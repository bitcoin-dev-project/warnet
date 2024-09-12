{
  description = "Warnet python development environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
      in
      {
        devShells.default = pkgs.mkShell {
          nativeBuildInputs = with pkgs; [
            python3
            python3Packages.pip
            # K8 dependencies for local cluster deployment.
            minikube
            kubectl
            kubernetes-helm
          ];

          # Install project dependencies and executable.
          shellHook = ''
            # Create a virtual environment if it doesn't exist.
            if [ ! -d ".venv" ]; then
              python -m venv .venv
            fi
            
            # Activate the virtual environment.
            source .venv/bin/activate
            # Install the project in editable mode.
            pip install -e .

            echo "WARNET DEVELOPMENT SHELL ENABLED"
          '';
        };
      }
    );
}
