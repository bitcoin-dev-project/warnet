use anyhow::Context;
use ini::Ini;
use serde_json::Value;
use std::path::Path;

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

pub fn parse_bitcoin_conf(file_path: Option<&Path>) -> Ini {
    Ini::load_from_file(file_path.unwrap()).expect("Failed to load or parse the file")
}

pub fn dump_bitcoin_conf(conf: &Ini) -> String {
    let mut entries = Vec::new();

    // Global section
    let global = conf.general_section();
    for (key, value) in global.iter() {
        entries.push(format!("{}={}", key, value));
    }

    // named sections (networks)
    for (section, properties) in conf.iter() {
        if let Some(section_name) = section {
            // Add section name as part of the output for non-global sections
            // Skip or handle differently if your format does not require section names
            entries.push(format!("[{}]", section_name));
            for (key, value) in properties.iter() {
                entries.push(format!("{}={}", key, value));
            }
        }
    }

    entries.join(",")
}
