import click
from dotenv import load_dotenv

# Load environment variables before importing any other modules
load_dotenv()

from src.analyst import run_analysis

@click.command()
@click.option('--url', required=True, help='The URL to process')
def main(url):
    """Process the given URL and output an analyst summary."""
    print("\n[+] Starting analysis for the URL you provided...")
    
    # Run the top-level orchestration pipeline
    summary = run_analysis(url)
    
    print("\n[+] Analysis complete! Output reports have been generated:")
    print("  -> 1-Page Summary Report: final_summary.md")
    print("  -> Analyst JSON Log:     analyst_summary_log.txt")
    print("  -> Run Cost History:      cost_log.txt\n")

if __name__ == '__main__':
    main()
