import discord
import requests
from bs4 import BeautifulSoup
import asyncio
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
import os
from dotenv import load_dotenv

load_dotenv()

# Discord bot token and channel ID
DISCORD_TOKEN = os.getenv("TOKEN")  # Replace with your bot's token
CHANNEL_ID = int(os.getenv('FREELANCER_CHANNEL_ID'))  # Replace with your Discord channel ID

# Freelancer job search URL (modify filters as needed)
FREELANCER_URL = 'https://www.freelancer.com/jobs/?fixed=true&hourly=true&languages=en'  # Example: Python jobs

# SQLAlchemy setup
Base = declarative_base()
engine = create_engine('sqlite:///freelancer_jobs.db')
Session = sessionmaker(bind=engine)

class Job(Base):
    __tablename__ = 'freelancer_jobs'
    
    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    link = Column(String, unique=True, nullable=False)
    description = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(engine)

class FreelancerJobBot(discord.Client):
    def __init__(self, **options):
        super().__init__(**options)
        self.bg_task = None

    async def setup_hook(self):
        self.bg_task = self.loop.create_task(self.send_jobs_to_discord())

    async def fetch_jobs(self):
        try:
            response = requests.get(FREELANCER_URL)
            soup = BeautifulSoup(response.text, 'html.parser')
            job_cards = soup.find_all('div', class_='JobSearchCard-item')

            new_jobs = []
            for job in job_cards:
                title_element = job.find('a', class_='JobSearchCard-primary-heading-link')
                title = title_element.text.strip() if title_element else "No Title"
                link = f"https://www.freelancer.com{title_element['href']}" if title_element else "No Link"
                description_element = job.find('p', class_='JobSearchCard-primary-description')
                description = description_element.text.strip() if description_element else "No Description"
                new_jobs.append((title, link, description))


            print(f"New Jobs length", len(new_jobs))
            return new_jobs
        except Exception as e:
            print(f"Error fetching jobs: {e}")
            return []

    async def send_jobs_to_discord(self):
        await self.wait_until_ready()
        channel = self.get_channel(CHANNEL_ID)

        while not self.is_closed():
            print(f"Checking for new jobs at {datetime.now()}...")
            jobs = await self.fetch_jobs()

            session = Session()
            for title, link, description in jobs:
                existing_job = session.query(Job).filter_by(link=link).first()
                if not existing_job:
                    new_job = Job(title=title, link=link, description=description)
                    try:
                        session.add(new_job)
                        session.commit()
                        
                        embed = discord.Embed(title=title, url=link, description=description, color=0x00ff00)
                        embed.set_footer(text="Freelancer Job Alert")
                        await channel.send(embed=embed)
                        print(f"Sent job: {title}")
                    except IntegrityError:
                        session.rollback()
                        print(f"Job already exists: {title}")
                else: print(f"Existed")
            session.close()

            await asyncio.sleep(120)  # Check every 2 minutes

intents = discord.Intents.default()
intents.messages = True
client = FreelancerJobBot(intents=intents)

async def main():
    async with client:
        await client.start(DISCORD_TOKEN)

asyncio.run(main())
