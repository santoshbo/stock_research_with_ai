def main():
    """Launch the Streamlit application."""
    import subprocess
    import sys
    
    # Run Streamlit UI
    subprocess.run([
        sys.executable, "-m", "streamlit", "run",
        "src/ui/streamlit_app.py"
    ])


if __name__ == "__main__":
    main()
