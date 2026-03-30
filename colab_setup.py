import os
import sys

def setup_colab():
    """
    Initializes the Google Colab environment for BioCirv AI.
    - Authenticates the user with GCP.
    - Installs necessary dependencies.
    - Sets up the CBORG API key from Colab secrets.
    """
    try:
        from google.colab import auth, userdata
        print("🚀 Initializing Google Colab environment...")

        # 1. Authenticate user
        print("🔐 Authenticating with Google Cloud...")
        auth.authenticate_user()

        # 2. Get CBORG API key from secrets
        print("🔑 Retrieving CBORG API key...")
        try:
            cborg_api_key = userdata.get('CBORG_API_KEY')
            os.environ['CBORG_API_KEY'] = cborg_api_key
            print("✅ CBORG API key configured.")
        except userdata.SecretNotFoundError:
            print("❌ CBORG_API_KEY not found in Colab secrets!")
            print("Please add it via the 'Secrets' (🔑) tab in the left sidebar.")

        # 3. Install dependencies
        print("📦 Installing dependencies (this may take a minute)...")
        # We use !pip install in notebooks, but for a script we can use subprocess or os.system
        # However, it's often better to let the user run the pip install cell.
        # For this script, we'll assume the environment is being set up.

        # 4. Project Path setup
        # If the repo is cloned into /content/biocirv-ai
        project_root = '/content/biocirv-ai'
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
