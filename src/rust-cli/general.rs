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
    rpc_params: &Option<Vec<String>>,
    mut params: ObjectParams,
) -> anyhow::Result<()> {
    params
        .insert("node", node_index)
        .context("add node_index param")?;
    params
        .insert("method", method)
        .context("add method param")?;
    if let Some(p) = rpc_params {
        params.insert("params", p).context("add rpc params")?;
    }
    let data = match node_type {
        NodeType::LnCli => make_rpc_call("tank_bcli", params)
            .await
            .context("Failed to make RPC call LnCli")?,
        NodeType::BitcoinCli => make_rpc_call("tank_bcli", params)
            .await
            .context("Failed to make RPC call BitcoinCli")?,
    };
    pretty_print_value(&data).context("pretty print result")?;
    Ok(())
}

pub async fn handle_debug_log_command(node: &u64, mut params: ObjectParams) -> anyhow::Result<()> {
    params
        .insert("node", node)
        .context("add node_index param")?;
    let data =  make_rpc_call("tank_debug_log", params)
            .await
            .context("Failed to make RPC call tank_debug_log")?;
    pretty_print_value(&data).context("pretty print result")?;
    Ok(())

}

pub async fn handle_messages_command(node_a: &u64, node_b: &u64, mut params: ObjectParams) -> anyhow::Result<()> {
    params
        .insert("node_a", node_a)
        .context("add node_b param")?;
    params
        .insert("node_b", node_b)
        .context("add node_b param")?;
    let data =  make_rpc_call("tank_messages", params)
            .await
            .context("Failed to make RPC call tank_messages")?;
    pretty_print_value(&data).context("pretty print result")?;
    Ok(())

}

pub async fn handle_grep_logs_command(pattern: &String, mut params: ObjectParams) -> anyhow::Result<()> {
    params
        .insert("pattern", pattern)
        .context("add pattern param")?;
    let data =  make_rpc_call("logs_grep", params)
            .await
            .context("Failed to make RPC call tank_messages")?;
    pretty_print_value(&data).context("pretty print result")?;
    Ok(())

}
