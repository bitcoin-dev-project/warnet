use crate::rpc_call::make_rpc_call;
use anyhow::Context;
use jsonrpsee::core::params::ObjectParams;

use crate::util::pretty_print_value;

pub enum NodeType {
    LnCli,
    BitcoinCli,
}

pub async fn handle_rpc_commands(
    node_type: NodeType,
    node_index: &u64,
    method: &String,
    params: &Option<Vec<String>>,
    network: &String,
) -> anyhow::Result<()> {
    let mut rpc_params = ObjectParams::new();
    rpc_params
        .insert("node", node_index)
        .context("add node_index param")?;
    rpc_params
        .insert("method", method)
        .context("add method param")?;
    if let Some(p) = params {
        rpc_params.insert("params", p).context("add rpc params")?;
    }
    rpc_params
        .insert("network", network)
        .context("add network param")?;
    let data = match node_type {
        NodeType::LnCli => make_rpc_call("tank_bcli", rpc_params)
            .await
            .context("Failed to make RPC call LnCli")?,
        NodeType::BitcoinCli => make_rpc_call("tank_bcli", rpc_params)
            .await
            .context("Failed to make RPC call BitcoinCli")?,
    };
    pretty_print_value(&data).context("pretty print result")?;
    Ok(())
}

pub async fn handle_debug_log_command(node: &u64, network: &String) -> anyhow::Result<()> {
    let mut rpc_params = ObjectParams::new();
    rpc_params
        .insert("node", node)
        .context("add node_index param")?;
    rpc_params
        .insert("network", network)
        .context("add network param")?;
    let data =  make_rpc_call("tank_debug_log", rpc_params)
            .await
            .context("Failed to make RPC call tank_debug_log")?;
    pretty_print_value(&data).context("pretty print result")?;
    Ok(())

}
