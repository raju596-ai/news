import asyncio
import sys
from datetime import datetime, timezone
from news.agents.single_agent import NewsRetrievalAgent


async def main_async():
    # Ensure Windows console prints UTF-8 characters without charmap errors
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    print("=" * 80)
    print("  ENTERPRISE REAL-TIME NEWS INTELLIGENCE AGENT (24-Hour Freshness)")
    print("=" * 80)
    print(f"Current System Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("Initializing LangGraph News Agent...")
    print("Primary LLM: Gemini (gemini-3.8-flash) | Fallback: Groq (llama-3.1-8b-instant)")
    print("-" * 80)

    agent = NewsRetrievalAgent()
    print("Fetching and validating real-time feeds from Worldwide and India...")
    report = await agent.run()

    print("\n" + "#" * 80)
    print(f"  NEWS INTELLIGENCE REPORT | DATE: {report.report_date}")
    print(f"  LLM Provider Used: {report.llm_provider_used}")
    print(f"  Fallback Activated: {'YES' if report.fallback_occurred else 'NO'}")
    print(f"  Execution Time: {report.execution_time_seconds}s")
    print("#" * 80 + "\n")

    print("================================================================================")
    print("  TOP 5 WORLDWIDE NEWS (LAST 24 HOURS)")
    print("================================================================================")
    for idx, article in enumerate(report.worldwide_news, 1):
        print(f"\n[{idx}] {article.title}")
        print(f"    Source:      {article.source} | Category: {article.category}")
        print(f"    Published:   {article.published_at}")
        print(f"    Summary:     {article.summary}")
        if article.key_points:
            print("    Highlights:")
            for pt in article.key_points:
                print(f"      * {pt}")
        print(f"    URL:         {article.url}")

    print("\n" + "=" * 80)
    print("  TOP 5 INDIA NEWS (LAST 24 HOURS)")
    print("================================================================================")
    for idx, article in enumerate(report.india_news, 1):
        print(f"\n[{idx}] {article.title}")
        print(f"    Source:      {article.source} | Category: {article.category}")
        print(f"    Published:   {article.published_at}")
        print(f"    Summary:     {article.summary}")
        if article.key_points:
            print("    Highlights:")
            for pt in article.key_points:
                print(f"      * {pt}")
        print(f"    URL:         {article.url}")

    print("\n" + "=" * 80)
    print("  END OF REPORT")
    print("=" * 80 + "\n")


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
