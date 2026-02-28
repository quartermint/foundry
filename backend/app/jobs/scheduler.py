import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.jobs.reddit_scraper import scrape_reddit
from app.jobs.youtube_scraper import scrape_youtube
from app.jobs.makerworld_trending import scrape_trending

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


def start_scheduler():
    """Start all background jobs."""
    # Reddit: every 12 hours
    scheduler.add_job(scrape_reddit, "interval", hours=12, id="reddit_scraper", replace_existing=True)

    # YouTube: every 7 days
    scheduler.add_job(scrape_youtube, "interval", days=7, id="youtube_scraper", replace_existing=True)

    # MakerWorld trending: every 24 hours
    scheduler.add_job(scrape_trending, "interval", hours=24, id="makerworld_trending", replace_existing=True)

    scheduler.start()
    logger.info("Background scheduler started with 3 jobs")


def stop_scheduler():
    """Shut down the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Background scheduler stopped")
