group "all" {
  targets = [
    "bitcoin-28-1",
    "bitcoin-27",
    "bitcoin-26",
    "v0-21-1",
    "v0-20-0",
    "v0-19-2",
    "v0-17-0",
    "v0-16-1",
    "bitcoin-unknown-message",
    "bitcoin-invalid-blocks",
    "bitcoin-50-orphans",
    "bitcoin-no-mp-trim",
    "bitcoin-disabled-opcodes",
    "bitcoin-5k-inv"
  ]
}

group "maintained" {
  targets = [
    "bitcoin-28-1",
    "bitcoin-27",
    "bitcoin-26"
  ]
}

group "practice" {
  targets = [
    "bitcoin-unknown-message",
    "bitcoin-invalid-blocks",
    "bitcoin-50-orphans",
    "bitcoin-no-mp-trim",
    "bitcoin-disabled-opcodes",
    "bitcoin-5k-inv"
  ]
}

group "vulnerable" {
  targets = [
    "v0-21-1",
    "v0-20-0",
    "v0-19-2",
    "v0-17-0",
    "v0-16-1",
  ]
}

target "maintained-base" {
  context = "./resources/images/bitcoin"
  args = {
    REPO = "bitcoin/bitcoin"
    BUILD_ARGS = "--disable-tests --without-gui --disable-bench --disable-fuzz-binary --enable-suppress-external-warnings"
  }
  platforms = ["linux/amd64", "linux/arm64", "linux/arm/v7"]
}

target "cmake-base" {
  inherits = ["maintained-base"]
  dockerfile = "./Dockerfile.dev"
  args = {
    BUILD_ARGS = "-DBUILD_TESTS=OFF -DBUILD_GUI=OFF -DBUILD_BENCH=OFF -DBUILD_UTIL=ON -DBUILD_FUZZ_BINARY=OFF -DWITH_ZMQ=ON"
  }
}

target "autogen-base" {
  inherits = ["maintained-base"]
  dockerfile = "./Dockerfile"
}

target "bitcoin-28-1" {
  inherits = ["autogen-base"]
  tags = ["bitcoindevproject/bitcoin:28.1"]
  args = {
    COMMIT_SHA = "32efe850438ef22e2de39e562af557872a402c31"
  }
}

target "bitcoin-27" {
  inherits = ["autogen-base"]
  tags = ["bitcoindevproject/bitcoin:27.2"]
  args = {
    COMMIT_SHA = "bf03c458e994abab9be85486ed8a6d8813313579"
  }
}

target "bitcoin-26" {
  inherits = ["autogen-base"]
  tags = ["bitcoindevproject/bitcoin:26.2"]
  args = {
    COMMIT_SHA = "7b7041019ba5e7df7bde1416aa6916414a04f3db"
  }
}

target "practice-base" {
  dockerfile = "./Dockerfile"
  context = "./resources/images/bitcoin/insecure"
  contexts = {
      bitcoin-src = "."
  }
  args = {
    ALPINE_VERSION = "3.20"
    BITCOIN_VERSION = "28.1.1"
    EXTRA_PACKAGES = "sqlite-dev"
    EXTRA_RUNTIME_PACKAGES = ""
    REPO = "willcl-ark/bitcoin"
  }
  platforms = ["linux/amd64", "linux/armhf"]
}

target "bitcoin-unknown-message" {
  inherits = ["practice-base"]
  tags = ["bitcoindevproject/bitcoin:99.0.0-unknown-message"]
  args = {
    COMMIT_SHA = "ae999611026e941eca5c0b61f22012c3b3f3d8dc"
  }
}

target "bitcoin-invalid-blocks" {
  inherits = ["practice-base"]
  tags = ["bitcoindevproject/bitcoin:98.0.0-invalid-blocks"]
  args = {
    COMMIT_SHA = "9713324368e5a966ec330389a533ae8ad7a0ea8f"
  }
}

target "bitcoin-50-orphans" {
  inherits = ["practice-base"]
  tags = ["bitcoindevproject/bitcoin:97.0.0-50-orphans"]
  args = {
    COMMIT_SHA = "cbcb308eb29621c0db3a105e1a1c1788fb0dab6b"
  }
}

target "bitcoin-no-mp-trim" {
  inherits = ["practice-base"]
  tags = ["bitcoindevproject/bitcoin:96.0.0-no-mp-trim"]
  args = {
    COMMIT_SHA = "a3a15a9a06dd541d1dafba068c00eedf07e1d5f8"
  }
}

target "bitcoin-disabled-opcodes" {
  inherits = ["practice-base"]
  tags = ["bitcoindevproject/bitcoin:95.0.0-disabled-opcodes"]
  args = {
    COMMIT_SHA = "5bdb8c52a8612cac9aa928c84a499dd701542b2a"
  }
}

target "bitcoin-5k-inv" {
  inherits = ["practice-base"]
  tags = ["bitcoindevproject/bitcoin:94.0.0-5k-inv"]
  args = {
    COMMIT_SHA = "e70e610e07eea3aeb0c49ae0bd9f4049ffc1b88c"
  }
}

target "CVE-base" {
  dockerfile = "./Dockerfile"
  context = "./resources/images/bitcoin/insecure"
  contexts = {
      bitcoin-src = "."
  }
  platforms = ["linux/amd64", "linux/armhf"]
  args = {
    REPO = "josibake/bitcoin"
  }
}

target "v0-16-1" {
  inherits = ["CVE-base"]
  tags = ["bitcoindevproject/bitcoin:0.16.1"]
  args = {
    ALPINE_VERSION = "3.7"
    BITCOIN_VERSION = "0.16.1"
    COMMIT_SHA = "dc94c00e58c60412a4e1a540abdf0b56093179e8"
    EXTRA_PACKAGES = "protobuf-dev libressl-dev"
    EXTRA_RUNTIME_PACKAGES = "boost boost-program_options libressl"
    PRE_CONFIGURE_COMMANDS = "sed -i '/AC_PREREQ/a\\AR_FLAGS=cr' src/univalue/configure.ac && sed -i '/AX_PROG_CC_FOR_BUILD/a\\AR_FLAGS=cr' src/secp256k1/configure.ac && sed -i 's:sys/fcntl.h:fcntl.h:' src/compat.h"
  }
}

target "v0-17-0" {
  inherits = ["CVE-base"]
  tags = ["bitcoindevproject/bitcoin:0.17.0"]
  args = {
    ALPINE_VERSION = "3.9"
    BITCOIN_VERSION = "0.17.0"
    COMMIT_SHA = "f6b2db49a707e7ad433d958aee25ce561c66521a"
    EXTRA_PACKAGES = "protobuf-dev libressl-dev"
    EXTRA_RUNTIME_PACKAGES = "boost boost-program_options libressl sqlite-dev"
  }
}

target "v0-19-2" {
  inherits = ["CVE-base"]
  tags = ["bitcoindevproject/bitcoin:0.19.2"]
  args = {
    ALPINE_VERSION = "3.12.12"
    BITCOIN_VERSION = "0.19.2"
    COMMIT_SHA = "e20f83eb5466a7d68227af14a9d0cf66fb520ffc"
    EXTRA_PACKAGES = "sqlite-dev libressl-dev"
    EXTRA_RUNTIME_PACKAGES = "boost boost-program_options libressl sqlite-dev"
  }
}

target "v0-20-0" {
  inherits = ["CVE-base"]
  tags = ["bitcoindevproject/bitcoin:0.20.0"]
  args = {
    ALPINE_VERSION = "3.12.12"
    BITCOIN_VERSION = "0.20.0"
    COMMIT_SHA = "0bbff8feff0acf1693dfe41184d9a4fd52001d3f"
    EXTRA_PACKAGES = "sqlite-dev miniupnpc-dev"
    EXTRA_RUNTIME_PACKAGES = "boost-filesystem miniupnpc-dev sqlite-dev"
  }
}

target "v0-21-1" {
  inherits = ["CVE-base"]
  tags = ["bitcoindevproject/bitcoin:0.21.1"]
  args = {
    ALPINE_VERSION = "3.17"
    BITCOIN_VERSION = "0.21.1"
    COMMIT_SHA = "e0a22f14c15b4877ef6221f9ee2dfe510092d734"
    EXTRA_PACKAGES = "sqlite-dev"
    EXTRA_RUNTIME_PACKAGES = "boost-filesystem sqlite-dev"
  }
}
