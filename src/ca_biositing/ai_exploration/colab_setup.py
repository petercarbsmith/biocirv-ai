import os
import sys

def get_secret(secret_id, project_id="biocirv-470318"):
    """Fetches a secret from GCP Secret Manager."""
    try:
        from google.cloud import secretmanager
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        print(f"ℹ️ Could not fetch secret '{secret_id}' from Secret Manager: {e}")
        return None

def setup_colab():
    """
    Initializes the Google Colab environment for BioCirv AI.
    - Authenticates the user with GCP.
    - Installs necessary dependencies.
    - Sets up the CBORG API key from Secret Manager, .env, or Colab secrets.
    """
    try:
        from google.colab import auth, userdata
        print("🚀 Initializing Google Colab environment...")

        # 1. Authenticate user
        print("🔐 Authenticating with Google Cloud...")
        try:
            auth.authenticate_user()
        except Exception as e:
            print(f"⚠️ Warning: Google Auth failed or was skipped: {e}")

        # 2. Get CBORG API key
        print("🔑 Checking for CBORG API key...")
        
        # Priority 1: Check if it's already in os.environ
        cborg_api_key = os.getenv('CBORG_API_KEY')
        
        # Priority 2: Try GCP Secret Manager (Most secure for VS Code/Headless)
        if not cborg_api_key:
            cborg_api_key = get_secret("CBORG_API_KEY")
            if cborg_api_key:
                os.environ['CBORG_API_KEY'] = cborg_api_key
                print("✅ CBORG API key retrieved securely from GCP Secret Manager.")

        # Priority 3: Try loading .env from multiple possible locations
        project_root = '/content/biocirv-ai'
        search_paths = [os.getcwd(), project_root, '/content']
        
        if not cborg_api_key:
            for path in search_paths:
                env_path = os.path.join(path, '.env')
                if os.path.exists(env_path):
                    try:
                        from dotenv import load_dotenv
                        load_dotenv(env_path, override=True)
                        cborg_api_key = os.getenv('CBORG_API_KEY')
                        if cborg_api_key:
                            print(f"✅ CBORG API key loaded from {env_path}.")
                            break
                    except ImportError:
                        print("ℹ️ python-dotenv not installed, skipping .env check.")
                        break

        # Priority 4: Check Colab secrets (Only works in UI)
        if not cborg_api_key:
            try:
                cborg_api_key = userdata.get('CBORG_API_KEY')
                os.environ['CBORG_API_KEY'] = cborg_api_key
                print("✅ CBORG API key retrieved from Colab secrets.")
            except BaseException as e:
                print(f"ℹ️ Skip fetching from Colab secrets (Reason: {type(e).__name__}).")

        if not os.getenv('CBORG_API_KEY'):
            print("❌ CBORG_API_KEY not found!")
            print("Please ensure you have stored the secret in GCP Secret Manager,")
            print("or provided a .env file, or added it to Colab 'Secrets' (🔑).")

        # 3. Project Path setup
        if os.path.exists(project_root):
            if project_root not in sys.path:
                sys.path.append(project_root)
                sys.path.append(f"{project_root}/src")
            print(f"📂 Project root added to sys.path: {project_root}")
        else:
            print(f"⚠️ Warning: {project_root} not found. Ensure the repository is cloned.")

        print("✨ Colab setup complete!")

    except ImportError:
        print("ℹ️ Not running in Google Colab environment. Skipping Colab-specific setup.")

if __name__ == "__main__":
    setup_colab()
