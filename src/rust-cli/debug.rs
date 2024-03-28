use jsonrpsee::core::params::ObjectParams;
use std::path::PathBuf;
use anyhow::Context;

use clap::Subcommand;

use crate::rpc_call::make_rpc_call;

#[derive(Subcommand, Debug)]
pub enum DebugCommands {
    /// Generate the docker-compose file for a given <graph_file> and return it.
    GenerateCompose { graph_file_path: PathBuf },
}

pub async fn handle_debug_command(command: &DebugCommands, network: &String) -> anyhow::Result<()> {
    let mut params = ObjectParams::new();
    params.insert("network", network).context("Add network to params")?;
    match command {
        DebugCommands::GenerateCompose { graph_file_path } => {
            params.insert("graph_file", graph_file_path.to_str()).context("Add graph file path to params")?;
            let data = make_rpc_call("generate_compose", params).await?;
            println!("Docker-compose file generated: {:?}", data);
        }
    }
    Ok(())
}
