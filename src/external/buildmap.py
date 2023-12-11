"""
TAKEN FROM https://github.com/sipa/asmap/tree/nextgen
"""

"""
Intake a map of IP prefixes -> AS numbers and output instructions that will
allow a decoder to match an IP address to an ASN by following a sequence
of instructions.
The instructions describe a prefix tree that can be navigated using the bits of
an IP address (i.e. 0 for left child, 1 for right child, leaf nodes
corresponding to a given ASN). The types of instructions are denoted by the
*Type() functions defined below. Once an IP address specifies a bit for which
there is no path in the tree (i.e. the part of its address more specific than
any known network prefix), the tree returns a "default" ASN value that has been
set based on the last valid location in the tree.
See `testmap.py:Interpret` for an illustration of how the decoding process
works.
Before the prefix tree is encoded into instructions using bits, it is compacted
(e.g. duplicate subtrees removed) and annotated with which default ASN values
should be set for particular regions of the tree.
"""
import sys
import ipaddress
from collections import namedtuple
from typing import Counter


def Parse(entries: list):
    """
    Read in a file of the format
        1.0.0.0/24 AS13335 # ipv4.dump:4856343
        1.0.4.0/22 AS56203 # ipv4.dump:2759291
        ...
    Ignoring comments following '#'. Creates an Entry object for each line.
    Maps IPv4 networks into IPv6 space.
    Args:
        entries: modified in place with the new Entrys.
    """
    for line in sys.stdin:
        line = line.split("#")[0].lstrip(" ").rstrip(" \r\n")
        prefix, asn = line.split(" ")
        assert len(asn) > 2 and asn[:2] == "AS"
        network = ipaddress.ip_network(prefix)

        prefix_len = network.prefixlen
        net_addr = int.from_bytes(network.network_address.packed, "big")

        # Map an IPv4 prefix into IPv6 space.
        if isinstance(network, ipaddress.IPv4Network):
            prefix_len += 96
            net_addr += 0xFFFF00000000

        entries.append(Entry(prefix_len, net_addr, int(asn[2:])))


Entry = namedtuple(
    "Entry",
    (
        # The length of the network prefix in bits. E.g. '26' for 255.255.0.0/26.
        "prefix_len",
        # An int containing the bits of the network address.
        "net_addr",
        # An int for the autonomous system (AS) number.
        "asn",
    ),
)


def UpdateTree(gtree, addrlen: int, entries: [Entry]):
    """
    Returns a prefix tree such that following a path down through the
    tree based on the bits of a network prefix (in order of most significant
    bit) leads to an ASN.
    Args:
        gtree: tree structure to encode the mappings into. Modified in-place.
        addrlen: The maximum number of bits in a network address.
            This is 128 for IPv6 (16 bytes).
        entries: The network prefix -> ASN mappings to encode.
    """
    for prefix, val, asn in sorted(entries):
        tree = gtree
        default = None

        # Iterate through each bit in the network prefix, starting with the
        # most significant bit.
        for i in range(prefix):
            bit = (val >> (addrlen - 1 - i)) & 1

            # If we have passed the end of the network prefix, all entries
            # under subsequent bits will be associated with the same ASN.
            needs_inner = i < prefix - 1
            if tree[bit] is None:
                if needs_inner:
                    tree[bit] = [default, default]
                    tree = tree[bit]
                    continue
                else:
                    tree[bit] = asn
                    break
            if isinstance(tree[bit], list):
                assert needs_inner
                tree = tree[bit]
                continue
            assert isinstance(tree[bit], int)
            if tree[bit] == asn:
                break
            if not needs_inner:
                tree[bit] = asn
                break
            default = tree[bit]
            tree[bit] = [default, default]
            tree = tree[bit]
    return gtree


def CompactTree(tree, approx=True) -> (list, set):
    """
    Remove redundancy from a tree.
    E.g. if all nodes in a subtree point to the same ASN, compact the subtree
    into a single int.
    Returns:
        (the compacted tree, a set of all ASNs in the tree)
    Args:
        approx: if True, unassigned ranges may get reassigned to arbitrary ASNs.
    """
    num = 0
    if tree is None:
        return (tree, set())
    if isinstance(tree, int):
        return (tree, set([tree]))
    tree[0], leftas = CompactTree(tree[0], approx)
    tree[1], rightas = CompactTree(tree[1], approx)
    allas = leftas | rightas
    if len(allas) == 0:
        return (None, allas)
    if approx and len(allas) == 1:
        return (list(allas)[0], allas)
    if isinstance(tree[0], int) and isinstance(tree[1], int) and tree[0] == tree[1]:
        return tree[0], set([tree[0]])
    return (tree, allas)


def PropTree(tree, approx=True) -> (list, Counter, bool):
    """
    Annotate internal nodes in the tree with the most common leafs below it.
    The binary serialization later uses this.
    This changes the shape of the `tree` datastructure from
    `[left_child, right_child]` to `[lc, rc, max_ASN_in_tree]`.
    Returns:
        (tree, Counter of ASNs in tree, whether or not tree is empty)
    """
    if tree is None:
        return (tree, Counter(), True)
    if isinstance(tree, int):
        return (tree, Counter({tree: 1}), False)
    tree[0], leftcnt, leftnone = PropTree(tree[0], approx)
    tree[1], rightcnt, rightnone = PropTree(tree[1], approx)
    allcnt = leftcnt + rightcnt
    allnone = leftnone | rightnone
    maxasn, maxcount = allcnt.most_common(1)[0]
    if maxcount is not None and maxcount >= 2 and (approx or not allnone):
        return ([tree[0], tree[1], maxasn], Counter({maxasn: 1}), allnone)
    return (tree, allcnt, allnone)


def EncodeBits(val, minval, bit_sizes) -> [int]:
    """
    Perform a variable-length encoding of a value to bits, least significant
    bit first.
    For each `bit_sizes` passed, attempt to encode the value with that number
    of bits + 1. Normalize the encoded value by `minval` to potentially save
    bits - the value will be corrected during decoding.
    Returns:
        a list of bits representing the value to encode.
    """
    val -= minval
    ret = []
    for pos in range(len(bit_sizes)):
        bit_size = bit_sizes[pos]

        # If the value will not fit in `bit_size` bits, absorb the largest
        # value for this bitsize and continue to the next smallest size.
        if val >= (1 << bit_size):
            val -= 1 << bit_size
            ret += [1]
        else:
            # If we aren't encoding the largest possible value per the largest
            # bitsize...
            if pos + 1 < len(bit_sizes):
                ret += [0]

            # Use remaining bits to encode the rest of val.
            for b in range(bit_size):
                ret += [(val >> (bit_size - 1 - b)) & 1]
            return ret

    # Couldn't fit val into any of the bit_sizes
    assert False


def MatchType() -> [int]:
    """
    The match instruction descends into the tree based on a bit path. If at any
    point the match fails to hit a valid path through the tree, it will fail
    and return the current default ASN (which changes as we move through the
    tree).
    """
    return EncodeType(2)


def JumpType() -> [int]:
    """
    The jump instruction allows us to quickly seek to one side of the tree
    or the other. By encoding the length of the left child, we can skip over
    it to the right child if need be.
    """
    return EncodeType(1)


def LeafType() -> [int]:
    """The leaf instruction encodes an ASN at the end of a bit path."""
    return EncodeType(0)


def SetNewDefaultType() -> [int]:
    """
    This instruction establishes a new default ASN to return should we fail
    while traversing this path.
    """
    return EncodeType(3)


def EncodeType(v) -> [int]:
    return EncodeBits(v, 0, [0, 0, 1])


def EncodeASN(v) -> [int]:
    # It's reasonable to ask why "15" (indicating 16 bits) is the minimum size
    # we might try to pack an ASN into, given there are many ASNs below 2**16.
    #
    # The reason that we start at 15 here is because we want the first bitsize
    # we specify to contain ~50% of the values we are trying to encode - this
    # is because each separate bitsize we try will add a digit to our encoded
    # values, so we simultaneously want to minimize the number of bitsizes we
    # allow while also minimizing the bit length of the encoded data, which
    # is a trade-off.
    return EncodeBits(v, 1, [15, 16, 17, 18, 19, 20, 21, 22, 23, 24])


def EncodeMatch(v) -> [int]:
    return EncodeBits(v, 2, [1, 2, 3, 4, 5, 6, 7, 8])


def EncodeJump(v) -> [int]:
    return EncodeBits(
        v,
        17,
        [
            5,
            6,
            7,
            8,
            9,
            10,
            11,
            12,
            13,
            14,
            15,
            16,
            17,
            18,
            19,
            20,
            21,
            22,
            23,
            24,
            25,
            26,
            27,
            28,
            29,
            30,
        ],
    )


def EncodeBytes(bits) -> [int]:
    """Encode a sequence of bits as a sequence of bytes."""
    val = 0
    nbits = 0
    bytes = []
    for bit in bits:
        val += bit << nbits
        nbits += 1
        if nbits == 8:
            bytes += [val]
            val = 0
            nbits = 0
    if nbits:
        bytes += [val]
    return bytes


def TreeSer(tree, default):
    match = 1
    assert tree is not None
    assert not (isinstance(tree, int) and tree == default)

    # If one side of the tree is empty (i.e. represents a path without
    # choices), encode a match instruction up to 8 bits.
    while isinstance(tree, list) and match <= 0xFF:
        if tree[0] is None or tree[0] == default:
            match = (match << 1) + 1
            tree = tree[1]
        elif tree[1] is None or tree[1] == default:
            match = (match << 1) + 0
            tree = tree[0]
        else:
            break
    if match >= 2:
        return MatchType() + EncodeMatch(match) + TreeSer(tree, default)

    # Leaf node: return the ASN.
    if isinstance(tree, int):
        return LeafType() + EncodeASN(tree)

    # Return the tree along with a new "default" ASN value should we fail to
    # match while along this path.
    if len(tree) > 2 and tree[2] != default:
        return SetNewDefaultType() + EncodeASN(tree[2]) + TreeSer(tree, tree[2])

    left = TreeSer(tree[0], default)
    right = TreeSer(tree[1], default)

    # Start the program by specifying a possible jump to either child of the
    # first node.
    return JumpType() + EncodeJump(len(left)) + left + right


def BuildTree(entries, approx=True):
    tree = [None, None]
    tree = UpdateTree(tree, 128, entries)
    return tree


if __name__ == "__main__":
    entries: [Entry] = []
    print("[INFO] Loading", file=sys.stderr)
    Parse(entries)
    print("[INFO] Read %i prefixes" % len(entries), file=sys.stderr)
    print("[INFO] Constructing trie", file=sys.stderr)
    tree = BuildTree(entries)
    print("[INFO] Compacting tree", file=sys.stderr)
    tree, _ = CompactTree(tree, True)
    print("[INFO] Computing inner prefixes", file=sys.stderr)
    tree, _, _ = PropTree(tree, True)

    ser = TreeSer(tree, None)
    print("[INFO] Total bits: %i" % (len(ser)), file=sys.stderr)
    sys.stdout.buffer.write(bytes(EncodeBytes(ser)))
