use prettytable::{Table, row};
use anyhow::Context;
use jsonrpsee::core::params::ObjectParams;
use clap::Subcommand;
use crate::rpc_call::make_rpc_call;

#[derive(Subcommand, Debug)]
pub enum ScenarioCommands {
    /// List available scenarios in the Warnet Test Framework
    Available {},
}

pub async fn handle_scenario_command(command: &ScenarioCommands, network: &String) -> anyhow::Result<()> {
    let mut params = ObjectParams::new();
    params.insert("network", network).context("Add network to params")?;

    match command {
        ScenarioCommands::Available {} => {
            let data = make_rpc_call("scenarios_available", params).await?;
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
    }
    Ok(())
}
