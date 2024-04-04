use jsonrpsee::{core::client::ClientT, http_client::HttpClientBuilder};

use serde_json::Value;

pub async fn make_rpc_call(
    request: &str,
    params: jsonrpsee::core::params::ObjectParams,
) -> anyhow::Result<serde_json::Value> {
    let url = "http://127.0.0.1:9276/api";
    let client = HttpClientBuilder::default().build(url)?;
    let response = client.request::<Value, _>(request, params).await?;
    Ok(response)
}
