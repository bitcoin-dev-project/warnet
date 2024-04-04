use anyhow::Context;
use jsonrpsee::core::params::ObjectParams;
use std::path::PathBuf;

use clap::Subcommand;

use crate::rpc_call::make_rpc_call;

#[derive(Subcommand, Debug)]
pub enum DebugCommand {
    /// Generate the docker-compose file for a given graph_file
    GenerateCompose {
        /// Path to graph file to generate from
        graph_file_path: PathBuf,
    },
}

pub async fn handle_debug_command(
    command: &DebugCommand,
    mut rpc_params: ObjectParams,
) -> anyhow::Result<()> {
    match command {
        DebugCommand::GenerateCompose { graph_file_path } => {
            rpc_params
                .insert("graph_file", graph_file_path.to_str())
                .context("Adding graph_file_path to rpc params")?;
            let data = make_rpc_call("generate_compose", rpc_params)
                .await
                .context("Calling generate_compose RPC")?;
            println!("Docker-compose file generated: {:?}", data);
        }
    }
    Ok(())
}
