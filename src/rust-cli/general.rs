use crate::rpc_call::make_rpc_call;
use anyhow::Context;
use jsonrpsee::core::params::ObjectParams;

use crate::util::pretty_print_value;

pub async fn handle_rpc_command(
    node: &u64,
    method: &String,
    params: &Option<Vec<String>>,
    network: &String,
) -> anyhow::Result<()> {
    let mut rpc_params = ObjectParams::new();
    rpc_params.insert("node", node).context("add node param")?;
    rpc_params
        .insert("method", method)
        .context("add method param")?;
    if let Some(p) = params {
        rpc_params.insert("params", p).context("add rpc params")?;
    }
    rpc_params
        .insert("network", network)
        .context("add network param")?;
    let data = make_rpc_call("tank_bcli", rpc_params)
        .await
        .context("Failed to make RPC call")?;
    pretty_print_value(&data).context("pretty print result")?;
    Ok(())
}
