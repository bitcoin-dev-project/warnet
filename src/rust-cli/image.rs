use anyhow::anyhow;
use clap::Subcommand;
use std::fs;
use std::process::{Command, Stdio};

#[derive(Subcommand, Debug)]
pub enum ImageCommand {
    /// Build bitcoind and bitcoin-cli from <repo>/<branch> as <registry>:<tag>.
    /// Optionally deploy to remote registry using --action=push, otherwise image is loaded to local registry.
    Build {
        #[arg(long)]
        repo: String,
        #[arg(long)]
        branch: String,
        #[arg(long)]
        registry: String,
        #[arg(long)]
        tag: String,
        #[arg(long)]
        build_args: Option<String>,
        #[arg(long)]
        arches: Option<String>,
        #[arg(long)]
        action: Option<String>,
    },
}

const ARCHES: [&str; 3] = ["amd64", "arm64", "armv7"];

fn run_command(command: &str) -> anyhow::Result<bool> {
    println!("Executing: {}", command);
    let mut child = Command::new("bash")
        .arg("-c")
        .arg(command)
        .stdout(Stdio::inherit())
        .stderr(Stdio::inherit())
        .spawn()?;

    let output = child.wait()?;

    if output.success() {
        Ok(true)
    } else {
        Err(anyhow!("Command failed"))
    }
}

fn build_image(
    repo: &String,
    branch: &String,
    docker_registry: &String,
    tag: &String,
    build_args: &Option<String>,
    arches: &Option<String>,
    action: &Option<String>,
) -> anyhow::Result<()> {
    let build_args = match build_args {
        Some(args) => format!("\"{}\"", args),
        None => "\"--disable-tests --without-gui --disable-bench --disable-fuzz-binary --enable-suppress-external-warnings \"".to_string(),
    };

    let mut build_arches = vec![];
    match arches {
        Some(a) => build_arches.extend(a.split(',').map(String::from)),
        None => build_arches.push("amd64".to_string()),
    }

    for arch in &build_arches {
        if !ARCHES.contains(&arch.as_str()) {
            println!("Error: {} is not a supported architecture", arch);
            return Err(anyhow!("Unsupported architecture: {}", arch));
        }
    }

    println!("repo={}", repo);
    println!("branch={}", branch);
    println!("docker_registry={}", docker_registry);
    println!("tag={}", tag);
    println!("build_args={}", build_args);
    println!("build_arches={:?}", build_arches);

    if !fs::metadata("src/templates")
        .map(|m| m.is_dir())
        .unwrap_or(false)
    {
        println!("Directory src/templates does not exist.");
        println!("Please run this script from the project root.");
        return Err(anyhow!("src/templates directory not found"));
    }

    let builder_name = "bitcoind-builder";
    let create_builder_cmd = format!("docker buildx create --name {} --use", builder_name);
    let creat_builder_res = run_command(&create_builder_cmd);
    if creat_builder_res.is_err() {
        let use_builder_cmd = format!("docker buildx use {}", builder_name);
        run_command(&use_builder_cmd)?;
    }

    let image_full_name = format!("{}:{}", docker_registry, tag);
    println!("image_full_name={}", image_full_name);

    let platforms = build_arches
        .iter()
        .map(|arch| format!("linux/{}", arch))
        .collect::<Vec<_>>()
        .join(",");

    let action = match action {
        Some(action) => action,
        None => "load",
    };
    let build_command = format!(
        "docker buildx build --platform {} --build-arg REPO={} --build-arg BRANCH={} --build-arg BUILD_ARGS={} --tag {} --file src/templates/Dockerfile . --{}",
        platforms, repo, branch, build_args, image_full_name, action
    );

    println!("Using build_command={}", build_command);

    let res = run_command(&build_command);
    if res.is_ok() {
        println!("Build completed");
    } else {
        println!("Build failed.");
    }

    let cleanup_builder_cmd = format!("docker buildx rm {}", builder_name);
    let cleanup_res = run_command(&cleanup_builder_cmd);
    if cleanup_res.is_ok() {
        println!("Buildx builder removed successfully.");
    } else {
        println!("Warning: Failed to remove the buildx builder.");
    }

    match res {
        Ok(true) => Ok(()),
        Ok(false) => Err(anyhow!(
            "Build command failed, but no specific error was provided."
        )),
        Err(e) => Err(anyhow!("Build command failed with error: {}", e)),
    }
}

pub async fn handle_image_command(command: &ImageCommand) -> anyhow::Result<()> {
    match command {
        ImageCommand::Build {
            repo,
            branch,
            registry,
            tag,
            build_args,
            arches,
            action,
        } => build_image(repo, branch, registry, tag, build_args, arches, action),
    }
}
