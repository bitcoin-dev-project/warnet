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
    /// Run a scenario file from remote repository (on warnet server)
    Run {
        /// Scenario name
        scenario: String,
        /// Arguments to scenario
        additional_args: Vec<String>,
    },
    /// Run a local scenario file by sending it to the server
    RunFile {
        /// Path to scenario file
        scenario_path: PathBuf,
        /// Arguments to scenario
        additional_args: Vec<String>,
    },
    /// List active scenarios
    Active {},
    /// Stop a scenario
    Stop {
        /// PID of scenario to stop
        pid: u64,
    },
}
async fn handle_available(params: ObjectParams) -> anyhow::Result<()> {
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
    Ok(())
}

async fn handle_run(
    mut params: ObjectParams,
    scenario: &str,
    additional_args: &Vec<String>,
) -> anyhow::Result<()> {
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
    Ok(())
}

async fn handle_run_file(
    mut params: ObjectParams,
    scenario_path: &PathBuf,
    additional_args: &Vec<String>,
) -> anyhow::Result<()> {
    let file_contents = std::fs::read(scenario_path).context("Failed to read scenario file")?;
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
    Ok(())
}

async fn handle_active(params: ObjectParams) -> anyhow::Result<()> {
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
    Ok(())
}

async fn handle_stop(mut params: ObjectParams, pid: &u64) -> anyhow::Result<()> {
    params.insert("pid", pid).context("Add pid to params")?;
    let data = make_rpc_call("scenarios_stop", params)
        .await
        .context("Failed to stop running scenario")?;
    if let serde_json::Value::String(message) = data {
        println!("{}", message);
    } else {
        println!("Unexpected response format.");
    }
    Ok(())
}

pub async fn handle_scenario_command(
    command: &ScenarioCommand,
    params: ObjectParams,
) -> anyhow::Result<()> {
    match command {
        ScenarioCommand::Available {} => {
            handle_available(params)
                .await
                .context("List available scenarios")?;
        }
        ScenarioCommand::Run {
            scenario,
            additional_args,
        } => {
            handle_run(params, scenario, additional_args)
                .await
                .context("Run scenario from remote")?;
        }

        ScenarioCommand::RunFile {
            scenario_path,
            additional_args,
        } => {
            handle_run_file(params, scenario_path, additional_args)
                .await
                .context("Run scenario file from path")?;
        }
        ScenarioCommand::Active {} => {
            handle_active(params)
                .await
                .context("List active scenarios")?;
        }
        ScenarioCommand::Stop { pid } => {
            handle_stop(params, pid)
                .await
                .context(format!("Stop running scenario with pid: {}", pid))?;
        }
    };
    Ok(())
}
