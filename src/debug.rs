use std::path::PathBuf;

use clap::Subcommand;
use jsonrpsee::rpc_params;

use crate::rpc_call::make_rpc_call;

#[derive(Subcommand, Debug)]
pub enum DebugCommands {
    /// Generate the docker-compose file for a given <graph_file> and return it.
    GenerateCompose { graph_file: PathBuf },
}

pub async fn handle_debug_command(command: &DebugCommands) -> anyhow::Result<()> {
    match command {
        DebugCommands::GenerateCompose { graph_file } => {
            let params = rpc_params![graph_file.to_string_lossy()];
            let data = make_rpc_call("generate_compose", params).await?;
            println!("Docker-compose file generated: {:?}", data);
        }
    }
    Ok(())
}
