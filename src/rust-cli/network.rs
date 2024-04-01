use anyhow::Context;
use base64::{engine::general_purpose, Engine as _};
use clap::Subcommand;
use jsonrpsee::core::params::ObjectParams;
use prettytable::{cell, Row, Table};
use serde_json::Value;
use std::path::PathBuf;

use crate::rpc_call::make_rpc_call;

#[derive(Subcommand, Debug)]
pub enum NetworkCommand {
    /// Start a network from a graph_file
    Start {
        /// Path to graph file
        graph_file: PathBuf,
        /// Force overwite config dir if already exists
        #[arg(long, short)]
        force: bool,
    },
    /// Bring a network back up
    Up {},
    /// Take a network down
    Down {},
    /// Get network info
    Info {},
    /// Shows the status of a network
    Status {},
    /// Return if network is connected
    Connected {},
    /// Export network details for sim-ln
    Export {},
}

fn graph_file_to_b64(graph_file: &PathBuf) -> anyhow::Result<String> {
    let file_contents = std::fs::read(graph_file).context("Failed to read graph file")?;
    Ok(general_purpose::STANDARD.encode(file_contents))
}

fn handle_network_status_response(data: serde_json::Value) {
    if let serde_json::Value::Array(items) = &data {
        for item in items {
            if let (Some(tank_index), Some(bitcoin_status)) = (
                item.get("tank_index").and_then(|v| v.as_i64()),
                item.get("bitcoin_status").and_then(|v| v.as_str()),
            ) {
                println!("Tank: {:<6} Bitcoin: {}", tank_index, bitcoin_status);
            } else {
                println!("Error: Response item is missing expected fields");
            }
        }
    } else {
        println!("Error: Expected an array in the response");
    }
}

fn handle_network_start_response(data: serde_json::Value) -> anyhow::Result<()> {
    // warnet table
    if let Some(warnet_headers) = data["warnet_headers"].as_array() {
        let mut table = Table::new();
        let headers: Vec<_> = warnet_headers
            .iter()
            .map(|header| header.as_str().unwrap_or(""))
            .collect();
        table.add_row(Row::new(
            headers.into_iter().map(|header| cell!(header)).collect(),
        ));
        // just used as fallback if warnet or its array content is missing
        let v: Vec<Value> = vec![Value::Null];

        if let Some(warnet) = data["warnet"].as_array().and_then(|row| row.first()) {
            let row_data: Vec<_> = match warnet.as_array() {
                Some(array) => array,
                None => &v,
            }
            .iter()
            .map(|item| item.as_str().unwrap_or(""))
            .collect();
            table.add_row(Row::new(
                row_data.into_iter().map(|row| cell!(row)).collect(),
            ));
        }
        table.printstd();
    }
    // tanks table
    if let Some(tank_headers) = data["tank_headers"].as_array() {
        let mut table = Table::new();
        let headers: Vec<_> = tank_headers
            .iter()
            .map(|header| header.as_str().unwrap_or(""))
            .collect();
        table.add_row(Row::new(
            headers.into_iter().map(|header| cell!(header)).collect(),
        ));

        let v: Vec<Value> = vec![Value::Null];
        if let Some(tanks) = data["tanks"].as_array() {
            for tank in tanks {
                let row_data: Vec<_> = match tank.as_array() {
                    Some(array) => array,
                    None => &v,
                }
                .iter()
                .map(|item| item.as_str().unwrap_or(""))
                .collect();
                table.add_row(Row::new(
                    row_data.into_iter().map(|row| cell!(row)).collect(),
                ));
            }
        }
        table.printstd();
    }
    Ok(())
}

pub async fn handle_network_command(
    command: &NetworkCommand,
    mut params: ObjectParams,
) -> anyhow::Result<()> {
    let (request, params) = match command {
        NetworkCommand::Start { graph_file, force } => {
            let b64_graph = graph_file_to_b64(graph_file).context("Read graph file")?;
            params
                .insert("graph_file", b64_graph)
                .context("Add base64 graph file to params")?;
            params
                .insert("force", *force)
                .context("Add force bool to params")?;
            ("network_from_file", params)
        }
        NetworkCommand::Up {} => ("network_up", params),
        NetworkCommand::Down {} => ("network_down", params),
        NetworkCommand::Info {} => ("network_info", params),
        NetworkCommand::Status {} => ("network_status", params),
        NetworkCommand::Connected {} => ("network_connected", params),
        NetworkCommand::Export {} => ("network_export", params),
    };

    let data = make_rpc_call(request, params).await?;
    match request {
        "network_status" => handle_network_status_response(data),
        "network_from_file" => {
            handle_network_start_response(data.clone())?;
        }
        _ => {
            println!("{}", data)
        }
    }
    // TODO: add response handling for other network commands
    Ok(())
}
