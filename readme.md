# Telegram Meeting Bot

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**Live demo:** [@GloriousMeetingBot](https://t.me/GloriousMeetingBot) on Telegram

A production-ready Telegram bot for organizing meetings with friends, teams, or colleagues. 
Built with a modular architecture, multi-language support, and external API integrations.

---

## 🎯 Key Features

| Feature | Description |
|---------|-------------|
| 📅 **Meeting Management** | Create, view, and delete meetings with date, time, place, and comments |
| 📨 **Invitations** | Invite users from the contact list, track responses (accepted/declined/pending) |
| 🌤️ **Weather Forecast** | Real-time weather forecast for the meeting time via OpenWeatherMap |
| 🤖 **AI Advice** | Get outfit recommendations based on weather using GPT-3.5 (OpenRouter) |
| ⏰ **Smart Reminders** | Automatic notifications 48h, 24h, 2h, and 1h before each meeting |
| 🌍 **Multi-language** | Full Russian/English support — time shown in MSK for RU, UTC for EN |
| 🛠️ **Admin Panel** | User management, admin rights, meeting moderation |
| 🚀 **Ready to Deploy** | Works on Render, Railway, or any Python hosting |

---

## 🧰 Tech Stack

- **Python 3.10+** — core language, async programming
- **python-telegram-bot** — Telegram Bot API framework
- **SQLite3** — lightweight embedded database
- **OpenWeatherMap API** — weather forecasts
- **OpenAI / OpenRouter API** — GPT-3.5 AI advice
- **JobQueue** — scheduled reminders
- **JSON i18n** — Russian/English localization
- **datetime / zoneinfo** — timezone handling (MSK ↔ UTC)
- **aiohttp + threading** — health check server for hosting
- **Render.com + UptimeRobot** — deployment and monitoring

---

## 📁 Project Evolution (5 Stages)

This repository shows the **full development journey** of the project:

| Stage | Focus | What was added |
|-------|-------|----------------|
| **1** | 🧱 Core functionality | Meeting creation, SQLite storage, meeting list |
| **2** | 🛡️ Administration | User management, admin rights, meeting cancellation |
| **3** | 🤖 External integrations | Weather forecast, 4-tier reminders |
| **4** | 🧹 Refactoring | Split into 9 modules — clean, maintainable architecture,AI advice |
| **5** | 🌍 Internationalization | Russian/English localization, UTC/MSK time zones |

Each stage has its own folder with a separate README for details.

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Telegram Bot Token (from [@BotFather](https://t.me/botfather))
- OpenWeatherMap API key
- OpenRouter API key (or OpenAI)

### Installation
```bash
git clone https://github.com/YOUR_USERNAME/meeting-bot.git
cd meeting-bot
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt