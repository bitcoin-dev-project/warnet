use crate::rpc_call::make_rpc_call;
use anyhow::Context;
use base64::{engine::general_purpose, Engine as _};
use clap::Subcommand;
use jsonrpsee::core::params::ObjectParams;
use prettytable::{row, Table};
use std::path::PathBuf;

#[derive(Subcommand, Debug)]
pub enum ScenarioCommand {
    /// List available scenarios in the Warnet Test Framework
    Available {},
    /// Run a scenario from remote repository with <name>
    Run {
        scenario: String,
        additional_args: Vec<String>,
    },
    /// Run a local scenario <file> by sending it to the server
    RunFile {
        scenario_path: PathBuf,
        additional_args: Vec<String>,
    },
    /// List active scenarios
    Active {},
    /// Stop a scenario with <PID>
    Stop { pid: u64 },
}

pub async fn handle_scenario_command(
    command: &ScenarioCommand,
    network: &String,
) -> anyhow::Result<()> {
    let mut params = ObjectParams::new();
    params
        .insert("network", network)
        .context("Add network to params")?;

    match command {
        ScenarioCommand::Available {} => {
            let data = make_rpc_call("scenarios_available", params)
                .await
                .context("Failed to fetch available scenarios")?;
            if let serde_json::Value::Array(scenarios) = data {
                let mut table = Table::new();
                table.add_row(row!["Scenario", "Description"]);
                for scenario in scenarios {
                    if let serde_json::Value::Array(details) = scenario {
                        if details.len() == 2 {
                            let name = details[0].as_str().unwrap_or("Unknown");
                            let description = details[1].as_str().unwrap_or("No description");
                            table.add_row(row![name, description]);
                        }
                    }
                }
                table.printstd();
            } else {
                println!("Unexpected response format.");
            }
        }
        ScenarioCommand::Run {
            scenario,
            additional_args,
        } => {
            params
                .insert("scenario", scenario)
                .context("Add scenario to params")?;
            params
                .insert("additional_args", additional_args)
                .context("Add additional_args to params")?;
            let data = make_rpc_call("scenarios_run", params)
                .await
                .context("Failed to run scenario")?;
            println!("{:?}", data);
        }

        ScenarioCommand::RunFile {
            scenario_path,
            additional_args,
        } => {
            let file_contents =
                std::fs::read(scenario_path).context("Failed to read scenario file")?;
            let scenario_base64 = general_purpose::STANDARD.encode(file_contents);
            params
                .insert("scenario_base64", scenario_base64)
                .context("Add scenario to params")?;
            params
                .insert("additional_args", additional_args)
                .context("Add additional_args to params")?;
            let data = make_rpc_call("scenarios_run_file", params)
                .await
                .context("Failed to run scenario")?;
            println!("{:?}", data);
        }
        ScenarioCommand::Active {} => {
            let data = make_rpc_call("scenarios_list_running", params)
                .await
                .context("Failed to list running scenarios")?;
            if let serde_json::Value::Array(scenarios) = data {
                let mut table = Table::new();
                table.add_row(row!["PID", "Command", "Network", "Active"]);
                for scenario in scenarios {
                    if let serde_json::Value::Object(details) = scenario {
                        let pid = details
                            .get("pid")
                            .and_then(|v| v.as_i64())
                            .map_or_else(|| "Unknown".to_string(), |v| v.to_string());
                        let cmd = details
                            .get("cmd")
                            .and_then(|v| v.as_str())
                            .unwrap_or("Unknown");
                        let network = details
                            .get("network")
                            .and_then(|v| v.as_str())
                            .unwrap_or("Unknown");
                        let active = details
                            .get("active")
                            .and_then(|v| v.as_bool())
                            .map_or_else(|| "Unknown".to_string(), |v| v.to_string());
                        table.add_row(row![pid, cmd, network, active]);
                    }
                }
                table.printstd();
            } else {
                println!("Unexpected response format.");
            }
        }
        ScenarioCommand::Stop { pid } => {
            params.insert("pid", pid).context("Add pid to params")?;
            let data = make_rpc_call("scenarios_stop", params)
                .await
                .context("Failed to stop running scenario")?;
            if let serde_json::Value::String(message) = data {
                println!("{}", message);
            } else {
                println!("Unexpected response format.");
            }
        }
    }
    Ok(())
}
