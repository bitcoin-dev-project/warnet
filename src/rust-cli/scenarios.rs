use crate::rpc_call::make_rpc_call;
use anyhow::Context;
use clap::Subcommand;
use jsonrpsee::core::params::ObjectParams;
use prettytable::{row, Table};

#[derive(Subcommand, Debug)]
pub enum ScenarioCommands {
    /// List available scenarios in the Warnet Test Framework
    Available {},
    Run {
        scenario: String,
        additional_args: Vec<String>,
    },
    Active {},
    Stop {
        pid: u64,
    },
}

pub async fn handle_scenario_command(
    command: &ScenarioCommands,
    network: &String,
) -> anyhow::Result<()> {
    let mut params = ObjectParams::new();
    params
        .insert("network", network)
        .context("Add network to params")?;

    match command {
        ScenarioCommands::Available {} => {
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
        ScenarioCommands::Run {
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
        ScenarioCommands::Active {} => {
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
        ScenarioCommands::Stop { pid } => {
            params.insert("pid", pid).context("Add pid to params")?;
            let data = make_rpc_call("scenarios_stop", params)
                .await
                .context("Failed to stop running scenario")?;
            println!("{:?}", data);
        }
    }
    Ok(())
}
