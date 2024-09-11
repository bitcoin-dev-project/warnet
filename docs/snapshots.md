# Creating and loading warnet snapshots

The `snapshot` command allows users to create snapshots of Bitcoin data directories from active bitcoin nodes. These snapshots can be used for backup purposes, to recreate specific network states, or to quickly initialize new bitcoin nodes with existing data.

## Usage Examples

### Snapshot a Specific bitcoin node

To create a snapshot of a specific bitcoin node:

```bash
warnet snapshot my-node-name -o <snapshots_dir>
```

This will create a snapshot of the bitcoin node named "my-node-name" in the `<snapshots_dir>`. If a directory the directory does not exist, it will be created. If no directory is specified, snapshots will be placed in `./warnet-snapshots` by default.

### Snapshot all nodes

To snapshot all running bitcoin nodes:

```bash
warnet snapshot --all -o `<snapshots_dir>`
```

### Use Filters

In the previous examples, everything in the bitcoin datadir was included in the snapshot, e.g., peers.dat. But there maybe use cases where only certain directories are needed. For example, assuming you only want to save the chain up to that point, you can use the filter argument:

```bash
warnet snapshot my-node-name --filter "chainstate,blocks"
```

This will create a snapshot containing only the 'blocks' and 'chainstate' directories. You would only need to snapshot this for a single node since the rest of the nodes will get this data via IBD when this snapshot is later loaded. A few other useful filters are detailed below:

```bash
# snapshot the logs from all nodes
warnet snapshot --all -f debug.log -o ./node-logs

# snapshot the chainstate and wallet from a mining node
# this is particularly userful for premining a signet chain that
# can be used later for starting a signet network
warnet snapshot mining-node -f "chainstate,blocks,wallets"

# snapshot only the wallets from a node
warnet snapshot my-node -f wallets

# snapshot a specific wallet
warnet snapshot my-node -f mining_wallet
```

## End-to-End Example

Here's a step-by-step guide on how to create a snapshot, upload it, and configure Warnet to use this snapshot when deploying. This particular example is for creating a premined signet chain:

1. Create a snapshot of the mining node:
   ```bash
   warnet snapshot miner --output /tmp/snapshots --filter "blocks,chainstate,wallets"
   ```

2. The snapshot will be created as a tar.gz file in the specified output directory. The filename will be in the format `{node_name}_{chain}_bitcoin_data.tar.gz`, i.e., `miner_bitcoin_data.tar.gz`.

3. Upload the snapshot to a location accessible by your Kubernetes cluster. This could be a cloud storage service like AWS S3, Google Cloud Storage, or a GitHub repository. If working in a warnet project directory, you can commit your snapshot in a `snapshots/` folder.

4. Note the URL of the uploaded snapshot, e.g., `https://github.com/your-username/your-repo/raw/main/my-warnet-project/snapshots/miner_bitcoin_data.tar.gz`

5. Update your Warnet configuration to use this snapshot. This involves modifying your `network.yaml` configuration file. Here's an example of how to configure the mining node to use the snapshot:

   ```yaml
   nodes:
     - name: miner
       image:
         tag: "27.0"
       loadSnapshot:
         enabled: true
         url: "https://github.com/your-username/your-repo/raw/main/snapshots/miner_bitcoin_data.tar.gz"
     # ... other nodes ...
   ```

6. Deploy Warnet with the updated configuration:
   ```bash
   warnet deploy networks/your_cool_network/network.yaml
   ```

7. Warnet will now use the uploaded snapshot to initialize the Bitcoin data directory when creating the "miner" node. In this particular example, the blocks will then be distibuted to the other nodes via IBD and the mining node can resume signet mining off the chaintip by loading the wallet from the snapshot:
   ```bash
   warnet bitcoin rpc miner loadwallet mining_wallet
   ```

## Notes

- Snapshots are specific to the chain (signet, regtest) of the bitcoin node they were created from. Ensure you're using snapshots with the correct network when deploying.
- Large snapshots may take considerable time to upload and download. Consider using filters to reduce snapshot size if you don't need the entire data directory.
- Ensure that your Kubernetes cluster has the necessary permissions to access the location where you've uploaded the snapshot.
- When using GitHub to host snapshots, make sure to use the "raw" URL of the file for direct download.
