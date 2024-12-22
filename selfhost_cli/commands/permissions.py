import os
import subprocess
import click

REPO_URL = "https://github.com/devzero-inc/self-hosted-tf.git"
REPO_DIR = "self-hosted-tf"
SCRIPT_PATH = "examples/permissions.sh"

def clone_repo():
    """Clones the required repository if it doesn't exist locally."""
    if not os.path.exists(REPO_DIR):
        click.echo(f"Cloning repository from {REPO_URL}...")
        subprocess.run(["git", "clone", REPO_URL], check=True)
    else:
        click.echo(f"Repository {REPO_DIR} already exists. Skipping clone.")

def run_permissions_script(deployment_type):
    """Runs the permissions.sh script, streams output, and sends input automatically."""
    script_path = os.path.join(REPO_DIR, SCRIPT_PATH)
    if not os.path.exists(script_path):
        raise FileNotFoundError(f"{script_path} not found. Ensure the repository is cloned correctly.")

    click.echo(f"Running permissions checker script for {deployment_type}...")

    try:
        # Make the script executable
        subprocess.run(["chmod", "+x", script_path], check=True)

        # Run the script and send input for the selected deployment type
        process = subprocess.Popen(
            [f"./{SCRIPT_PATH}"],
            cwd=REPO_DIR,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE  # Allows sending input
        )

        # Send the appropriate input (1 or 2) and capture output
        stdout, stderr = process.communicate(input=f"{deployment_type}\n", timeout=300)

        # Stream output
        click.echo(stdout)
        if stderr:
            click.echo(stderr, err=True)

        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, SCRIPT_PATH)
        else:
            click.echo("Permissions check completed successfully!")

    except subprocess.TimeoutExpired:
        click.echo("The script took too long to complete and was aborted.", err=True)
        process.terminate()
        raise
    except subprocess.CalledProcessError as e:
        click.echo(f"Error running the permissions check: {e}", err=True)
        raise
    except Exception as e:
        click.echo(f"Unexpected error: {str(e)}", err=True)
        raise

def check_aws_permissions(deployment_type):
    """Main function to check AWS permissions."""
    try:
        clone_repo()
        run_permissions_script(deployment_type)
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        raise click.Abort()