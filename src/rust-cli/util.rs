use anyhow::Context;
use serde_json::Value;

pub fn pretty_print_value(value: &Value) -> anyhow::Result<()> {
    match value {
        Value::String(inner_json) => {
            // Attempt to parse the string as JSON
            match serde_json::from_str::<Value>(inner_json) {
                Ok(parsed_inner) => {
                    // If parsing succeeds, pretty print the JSON
                    println!(
                        "{}",
                        serde_json::to_string_pretty(&parsed_inner)
                            .context("Failed to pretty print inner JSON")?
                    );
                }
                Err(_) => {
                    // If parsing fails, it's not valid JSON, so just print the string itself
                    println!("{}", inner_json);
                }
            }
        }
        // If `value` is not a string (i.e., already a JSON Value), pretty print it directly
        _ => println!(
            "{}",
            serde_json::to_string_pretty(&value).context("Failed to pretty print JSON")?
        ),
    }
    Ok(())
}
