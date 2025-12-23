# Real-Time User Monitoring & Alert System

A Python-based system for real-time user monitoring with automated alerting capabilities. This system monitors user activity and sends alerts via email and Slack when specific conditions are met.

## Features

- Real-time user monitoring
- Automated alert system (Email & Slack)
- Database integration (PostgreSQL)
- Web scraping capabilities using Selenium
- Logging and error tracking

## Requirements

- Python 3.11+
- PostgreSQL database
- Chrome browser (for Selenium WebDriver)

## Installation

1. Clone this repository:
```bash
git clone https://github.com/maheen2601/Real-Time-Monitoring.git
cd Real-Time-Monitoring
```

2. Create a virtual environment:
```bash
python -m venv venv
venv\Scripts\activate  # On Windows
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
   - Create a `config/.env` file with the following variables:
   ```
   DB_NAME=your_database_name
   DB_USER=your_database_user
   DB_PASS=your_database_password
   DB_HOST=your_database_host
   DB_PORT=your_database_port
   ```

5. Download ChromeDriver:
   - Download ChromeDriver from https://chromedriver.chromium.org/
   - Place `chromedriver.exe` in the project root directory

## Usage

Run the monitoring system:
```bash
run_monitor.bat
```

Or run the Python scripts directly:
```bash
python scripts/main.py
```

## Project Structure

```
.
├── scripts/              # Main Python scripts
│   ├── main.py          # Main entry point
│   ├── all_log.py       # Logging functionality
│   └── check_and_send_alerts.py  # Alert system
├── config/              # Configuration files
├── logs/                # Application logs
├── requirements.txt     # Python dependencies
└── README.md           # This file
```

## Configuration

- Database connection settings are configured in `config/.env`
- Alert thresholds and conditions can be modified in the respective script files
- Logging configuration is set in each script's logging setup

## License

This project is open source and available for use.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.


