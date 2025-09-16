# Installation and Setup

<cite>
**Referenced Files in This Document**   
- [requirements.txt](file://requirements.txt)
- [database.py](file://database.py)
- [Bot_new.py](file://Bot_new.py)
- [add_energy_drink_new.py](file://add_energy_drink_new.py)
- [config.py](file://config.py)
- [constants.py](file://constants.py)
</cite>

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Cloning the Repository](#cloning-the-repository)
3. [Installing Dependencies](#installing-dependencies)
4. [Configuring Environment Variables](#configuring-environment-variables)
5. [Initializing the SQLite Database](#initializing-the-sqlite-database)
6. [Obtaining and Configuring Telegram Bot Token](#obtaining-and-configuring-telegram-bot-token)
7. [Setting Up Webhook or Polling Mode](#setting-up-webhook-or-polling-mode)
8. [Preparing the Energy Drink Image Directory](#preparing-the-energy-drink-image-directory)
9. [Populating Initial Data](#populating-initial-data)
10. [Running the Application](#running-the-application)
11. [Common Setup Pitfalls and Troubleshooting](#common-setup-pitfalls-and-troubleshooting)
12. [Complete Working Example](#complete-working-example)

## Prerequisites

Before setting up the RELOAD bot environment, ensure you have the following prerequisites installed on your system:
- Python 3.8 or higher
- pip (Python package installer)
- Git (for cloning the repository)
- A Telegram account to create and manage bots

These tools are essential for successfully installing, configuring, and running the RELOAD bot.

## Cloning the Repository

To begin the setup process, clone the RELOAD bot repository from its source location. Open a terminal or command prompt and execute the following command:

```bash
git clone https://github.com/username/RELOAD.git
cd RELOAD
```

Replace `https://github.com/username/RELOAD.git` with the actual repository URL if different. This will download the entire project structure into a local directory named `RELOAD`.

**Section sources**
- [Bot_new.py](file://Bot_new.py)

## Installing Dependencies

The RELOAD bot relies on several Python packages specified in the `requirements.txt` file. Install these dependencies using pip by running the following command in the project root directory:

```bash
pip install -r requirements.txt
```

This command installs the required packages:
- `python-telegram-bot==20.7`: The core library for interacting with the Telegram Bot API.
- `python-dotenv==1.0.1`: A library for managing environment variables (though not actively used in current code).
- `SQLAlchemy>=2.0,<2.1`: An ORM for database interactions.

Ensure that the installation completes without errors. If you encounter permission issues, consider using a virtual environment or adding the `--user` flag to the pip command.

**Section sources**
- [requirements.txt](file://requirements.txt)

## Configuring Environment Variables

The RELOAD bot uses a configuration file to store sensitive information such as the Telegram bot token. Create a `config.py` file in the project root directory if it does not already exist, and define the `TOKEN` variable:

```python
TOKEN = "your_telegram_bot_token_here"
```

Replace `your_telegram_bot_token_here` with the actual token obtained from the BotFather on Telegram. This file is already present in the repository with a placeholder token, so update it accordingly.

Alternatively, you can use environment variables for better security. However, the current implementation directly reads from `config.py`. Ensure this file is not committed to version control by adding it to `.gitignore`.

**Section sources**
- [config.py](file://config.py)

## Initializing the SQLite Database

The RELOAD bot uses SQLite as its database backend. The database schema and tables are defined in `database.py`. To initialize the database, run the following command:

```bash
python database.py
```

However, since `database.py` does not contain a direct execution block for creating tables, ensure that the `create_db_and_tables()` function is called when the application starts. This function is automatically invoked in `add_energy_drink_new.py`, which ensures the database and all necessary tables are created if they do not exist.

The database file `bot_data.db` will be created in the project root directory. This file stores all bot data, including player information, energy drinks, inventory, and shop offers.

**Section sources**
- [database.py](file://database.py)

## Obtaining and Configuring Telegram Bot Token

To obtain a Telegram bot token, follow these steps:
1. Open Telegram and search for the `BotFather` bot.
2. Start a chat with BotFather and use the `/newbot` command to create a new bot.
3. Follow the prompts to name your bot and choose a username.
4. BotFather will provide a token in the format `1234567890:ABCdefGhIJKlmNoPQRsTUVwxyZ`. Copy this token.
5. Paste the token into the `config.py` file as shown in the previous section.

The token authenticates your bot with Telegram's servers and allows it to send and receive messages.

**Section sources**
- [config.py](file://config.py)

## Setting Up Webhook or Polling Mode

The RELOAD bot uses polling mode to receive updates from Telegram, as indicated by the absence of webhook configuration in `Bot_new.py`. Polling mode is simpler to set up and does not require a public HTTPS endpoint.

In `Bot_new.py`, the application is initialized and started using the following code:

```python
application = ApplicationBuilder().token(TOKEN).build()
# ... handlers are added ...
application.run_polling()
```

This configuration continuously polls Telegram's servers for new updates. No additional setup is required for polling mode. If you wish to switch to webhook mode, you would need to modify this code and provide a public URL with SSL certification, which is beyond the scope of this setup guide.

**Section sources**
- [Bot_new.py](file://Bot_new.py)

## Preparing the Energy Drink Image Directory

The bot displays images for each energy drink. These images are stored in the `energy_images` directory, as specified by the `ENERGY_IMAGES_DIR` constant in `constants.py`.

Create the directory if it does not exist:

```bash
mkdir energy_images
```

Place all energy drink images in this directory. Supported formats include PNG, JPG, and JPEG. When adding drinks via `add_energy_drink_new.py`, you will be prompted to select an image file, which will be copied into this directory.

Ensure that the images are named appropriately and do not contain spaces or special characters in their filenames to avoid path issues.

**Section sources**
- [constants.py](file://constants.py)
- [add_energy_drink_new.py](file://add_energy_drink_new.py)

## Populating Initial Data

To add energy drinks to the database, use the `add_energy_drink_new.py` script. This interactive script allows you to input drink details and associate images.

Run the script with:

```bash
python add_energy_drink_new.py
```

Follow the prompts:
1. Enter the name of the energy drink.
2. Provide a description.
3. Specify whether it is a 'Special' drink.
4. Choose an image file using the file dialog.

The script checks if a drink with the same name already exists and updates it if necessary. Otherwise, it creates a new entry. After each entry, the data is committed to the database.

Repeat this process to populate the database with initial energy drinks. At least one drink must be added for the bot to function properly, as searches and daily bonuses depend on available drinks.

**Section sources**
- [add_energy_drink_new.py](file://add_energy_drink_new.py)

## Running the Application

Once all setup steps are complete, start the RELOAD bot by running:

```bash
python Bot_new.py
```

This command initializes the application, connects to the Telegram API using the provided token, and begins polling for updates. The bot will be online and responsive to commands.

Open a chat with your bot on Telegram and send `/start` to verify that it responds with the main menu. If the bot does not respond, check the console output for error messages.

**Section sources**
- [Bot_new.py](file://Bot_new.py)

## Common Setup Pitfalls and Troubleshooting

### Missing Environment Variables
If the `config.py` file is missing or the `TOKEN` variable is not set, the bot will fail to start with an error indicating that `TOKEN` is not defined. Ensure that `config.py` exists and contains a valid token.

### Database Connection Issues
If the `bot_data.db` file cannot be created or accessed, verify that the application has write permissions in the project directory. On some systems, running the script with elevated privileges may be necessary.

### Incorrect File Permissions
Ensure that all Python files have the correct execution permissions. On Unix-like systems, use `chmod +x filename.py` if needed.

### Missing Dependencies
If you encounter `ModuleNotFoundError` exceptions, confirm that all dependencies listed in `requirements.txt` are installed. Re-run `pip install -r requirements.txt` to resolve missing packages.

### Image Path Errors
If energy drink images do not display, check that the `image_path` in the database matches the actual filename in the `energy_images` directory. Case sensitivity and file extensions must match exactly.

### Polling Conflicts
Running multiple instances of `Bot_new.py` can cause conflicts with polling. Ensure only one instance is running at a time.

## Complete Working Example

Follow this step-by-step example to set up the RELOAD bot from scratch:

1. Clone the repository:
   ```bash
   git clone https://github.com/username/RELOAD.git
   cd RELOAD
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Obtain a Telegram bot token from BotFather and update `config.py`:
   ```python
   TOKEN = "7827379395:AAGVwD7PvI_XHuzFESsGdPdh4cwUnxyJGu0"
   ```

4. Create the energy drink image directory:
   ```bash
   mkdir energy_images
   ```

5. Initialize the database and add initial drinks:
   ```bash
   python add_energy_drink_new.py
   ```
   Follow the prompts to add at least one energy drink with an image.

6. Start the bot:
   ```bash
   python Bot_new.py
   ```

7. Open Telegram, find your bot, and send `/start`. You should see the main menu with options to search for energy drinks, view inventory, and more.

This completes the setup process. The bot is now fully operational and ready for interaction.

**Section sources**
- [requirements.txt](file://requirements.txt)
- [database.py](file://database.py)
- [Bot_new.py](file://Bot_new.py)
- [add_energy_drink_new.py](file://add_energy_drink_new.py)
- [config.py](file://config.py)
- [constants.py](file://constants.py)