# Core System Architecture

<cite>
**Referenced Files in This Document**   
- [Bot_new.py](file://Bot_new.py)
- [database.py](file://database.py)
- [constants.py](file://constants.py)
- [admin.py](file://admin.py)
- [admin2.py](file://admin2.py)
- [fullhelp.py](file://fullhelp.py)
</cite>

## Table of Contents
1. [Introduction](#introduction)
2. [Project Structure](#project-structure)
3. [Core Components](#core-components)
4. [Architecture Overview](#architecture-overview)
5. [Detailed Component Analysis](#detailed-component-analysis)
6. [Dependency Analysis](#dependency-analysis)
7. [Performance Considerations](#performance-considerations)
8. [Troubleshooting Guide](#troubleshooting-guide)
9. [Conclusion](#conclusion)

## Introduction
The RELOAD application is a Telegram-based bot designed for energy drink collection and management. This document provides comprehensive architectural documentation for the core system, focusing on its modular design, separation of concerns, asynchronous event-driven architecture, and key design decisions. The system is orchestrated by Bot_new.py which integrates specialized modules for administration, help, and data management. The architecture follows a clean separation between presentation (Telegram commands), business logic (in Bot_new.py), data access (database.py using Repository pattern), and configuration (constants.py). The system leverages asyncio and the python-telegram-bot framework for asynchronous event handling.

## Project Structure
The RELOAD application follows a modular structure with clear separation of concerns. The main components are organized as individual Python files, each responsible for specific functionality. The core orchestrator (Bot_new.py) imports and integrates specialized modules for administration, help, and data management. Configuration is centralized in constants.py, while data access is handled through database.py which implements the Repository pattern. Administrative functions are split between admin.py and admin2.py based on privilege levels, and help functionality is encapsulated in fullhelp.py.

```mermaid
graph TD
Bot_new[Bot_new.py<br/>Main Orchestrator] --> database[database.py<br/>Data Access Layer]
Bot_new --> constants[constants.py<br/>Configuration]
Bot_new --> admin[admin.py<br/>Admin Commands]
Bot_new --> admin2[admin2.py<br/>Privileged Admin Commands]
Bot_new --> fullhelp[fullhelp.py<br/>Help System]
Bot_new --> add_energy[add_energy_drink_new.py<br/>Energy Drink Management]
Bot_new --> export[export_user_ids.py<br/>User Data Export]
Bot_new --> migrate[migrate_data.py<br/>Data Migration]
```

**Diagram sources**
- [Bot_new.py](file://Bot_new.py#L1-L50)
- [database.py](file://database.py#L1-L50)
- [constants.py](file://constants.py#L1-L10)

**Section sources**
- [Bot_new.py](file://Bot_new.py#L1-L100)
- [database.py](file://database.py#L1-L100)
- [constants.py](file://constants.py#L1-L76)

## Core Components
The RELOAD application's core system consists of several key components that work together to provide a seamless user experience. The main orchestrator (Bot_new.py) handles Telegram command routing and business logic execution. The data access layer (database.py) implements the Repository pattern for database operations, providing a clean abstraction between the business logic and data storage. Configuration is managed through constants.py which contains global constants used throughout the application. Administrative functionality is divided between admin.py (basic admin commands) and admin2.py (privileged admin commands), while help functionality is provided by fullhelp.py.

**Section sources**
- [Bot_new.py](file://Bot_new.py#L1-L100)
- [database.py](file://database.py#L1-L100)
- [constants.py](file://constants.py#L1-L76)
- [admin.py](file://admin.py#L1-L100)
- [admin2.py](file://admin2.py#L1-L100)
- [fullhelp.py](file://fullhelp.py#L1-L100)

## Architecture Overview
The RELOAD application follows a layered architecture with clear separation of concerns. The system is built on an asynchronous event-driven model using asyncio and the python-telegram-bot framework. The architecture consists of four main layers: presentation layer (Telegram commands), business logic layer (in Bot_new.py), data access layer (database.py using Repository pattern), and configuration layer (constants.py). This separation ensures maintainability and scalability of the application.

```mermaid
graph TD
subgraph "Presentation Layer"
Telegram[Telegram Commands<br/>/start, /find, /inventory]
end
subgraph "Business Logic Layer"
Bot_new[Bot_new.py<br/>Command Handlers<br/>Business Logic<br/>State Management]
end
subgraph "Data Access Layer"
database[database.py<br/>Repository Pattern<br/>SQLAlchemy ORM]
end
subgraph "Configuration Layer"
constants[constants.py<br/>Global Constants<br/>Game Parameters]
end
Telegram --> Bot_new
Bot_new --> database
Bot_new --> constants
database --> SQLite[(SQLite Database)]
```

**Diagram sources**
- [Bot_new.py](file://Bot_new.py#L1-L100)
- [database.py](file://database.py#L1-L100)
- [constants.py](file://constants.py#L1-L76)

## Detailed Component Analysis
This section provides a thorough analysis of each key component in the RELOAD application, including their interactions, design patterns, and implementation details.

### Bot_new.py Analysis
Bot_new.py serves as the main orchestrator of the RELOAD application, handling all Telegram command routing and implementing the core business logic. It follows an event-driven architecture using the python-telegram-bot framework's callback system. The module imports and integrates specialized modules for administration, help, and data management, creating a cohesive system from modular components.

#### For Object-Oriented Components:
```mermaid
classDiagram
class Bot_new {
+dict ADMIN_USER_IDS
+dict PENDING_ADDITIONS
+dict GIFT_OFFERS
+dict _LOCKS
+dict REJECT_PROMPTS
+dict TEXTS
+function _get_lock(key)
+function t(lang, key)
+function show_menu(update, context)
+function search_reminder_job(context)
+function auto_search_job(context)
+function _perform_energy_search(user_id, username, context)
+function find_energy(update, context)
+function claim_daily_bonus(update, context)
+function show_inventory(update, context)
+function show_stats(update, context)
+function settings_menu(update, context)
+function toggle_auto_search(update, context)
+function skip_photo(update, context)
}
class database {
+function create_db_and_tables()
+function get_or_create_player(user_id, username)
+function get_all_drinks()
+function get_player_inventory_with_details(user_id)
+function add_drink_to_inventory(user_id, drink_id, rarity)
+function update_player(user_id, **kwargs)
+function is_vip(user_id)
+function get_vip_until(user_id)
+function get_auto_search_daily_limit(user_id)
+function get_receipts_by_user_id(user_id)
+function get_tg_premium_stock()
+function add_tg_premium_stock(delta)
+function set_tg_premium_stock(value)
+function get_bonus_stock(kind)
+function add_bonus_stock(kind, delta)
+function set_bonus_stock(kind, value)
+function get_admin_users()
+function is_admin(user_id)
+function get_admin_level(user_id)
+function add_admin_user(user_id, username, level)
+function set_admin_level(user_id, level)
+function remove_admin_user(user_id)
+function insert_moderation_log(actor_id, action, request_id, target_id, details)
+function get_receipt_by_id(receipt_id)
+function verify_receipt(receipt_id, verified_by)
+function get_player_by_username(username)
+function add_auto_search_boost(user_id, count, days)
+function add_auto_search_boost_to_all(count, days)
+function get_boost_info(user_id)
+function get_boost_statistics()
+function get_expiring_boosts(hours_ahead)
+function get_user_boost_history(user_id, limit)
+function add_boost_history_record(user_id, username, action, boost_count, boost_days, granted_by, granted_by_username, details)
}
class constants {
+int SEARCH_COOLDOWN
+int DAILY_BONUS_COOLDOWN
+str ENERGY_IMAGES_DIR
+dict RARITIES
+dict COLOR_EMOJIS
+list RARITY_ORDER
+int ITEMS_PER_PAGE
+str VIP_EMOJI
+dict VIP_COSTS
+dict VIP_DURATIONS_SEC
+int TG_PREMIUM_COST
+int TG_PREMIUM_DURATION_SEC
+set ADMIN_USERNAMES
+int AUTO_SEARCH_DAILY_LIMIT
+float RECEIVER_COMMISSION
+dict RECEIVER_PRICES
+int SHOP_PRICE_MULTIPLIER
+dict SHOP_PRICES
}
Bot_new --> database : "uses"
Bot_new --> constants : "imports"
Bot_new --> admin : "imports"
Bot_new --> admin2 : "imports"
Bot_new --> fullhelp : "imports"
```

**Diagram sources**
- [Bot_new.py](file://Bot_new.py#L1-L100)
- [database.py](file://database.py#L1-L100)
- [constants.py](file://constants.py#L1-L76)

#### For API/Service Components:
```mermaid
sequenceDiagram
participant User as "Telegram User"
participant Bot as "Bot_new.py"
participant DB as "database.py"
participant Constants as "constants.py"
User->>Bot : /start command
Bot->>DB : get_or_create_player(user_id, username)
Bot->>Constants : t(lang, 'menu_title')
Bot->>Bot : show_menu(update, context)
Bot->>User : Display main menu with buttons
User->>Bot : Click "Find energy" button
Bot->>Bot : find_energy(update, context)
Bot->>Bot : _get_lock(f"user : {user.id} : search")
Bot->>DB : get_or_create_player(user_id, username)
Bot->>DB : is_vip(user_id)
Bot->>DB : get_all_drinks()
Bot->>Bot : Randomly select drink and determine rarity
Bot->>DB : add_drink_to_inventory(user_id, drink_id, rarity)
Bot->>DB : update_player(user_id, last_search, coins)
Bot->>Bot : Format result message with image and caption
Bot->>User : Send found energy drink with details
```

**Diagram sources**
- [Bot_new.py](file://Bot_new.py#L1-L100)
- [database.py](file://database.py#L1-L100)

**Section sources**
- [Bot_new.py](file://Bot_new.py#L1-L100)
- [database.py](file://database.py#L1-L100)
- [constants.py](file://constants.py#L1-L76)

### database.py Analysis
The database.py module implements the data access layer of the RELOAD application using the Repository pattern with SQLAlchemy ORM. It defines the database schema through declarative base classes and provides a comprehensive set of functions for data manipulation. The module handles all database operations, including player management, energy drink inventory, administrative functions, and bonus tracking.

#### For Object-Oriented Components:
```mermaid
classDiagram
class Player {
+BigInteger user_id
+String username
+Integer coins
+Integer last_search
+Integer last_bonus_claim
+Integer last_add
+String language
+Boolean remind
+Integer vip_until
+Integer tg_premium_until
+Boolean auto_search_enabled
+Integer auto_search_count
+Integer auto_search_reset_ts
+Integer auto_search_boost_count
+Integer auto_search_boost_until
+relationship inventory
}
class EnergyDrink {
+Integer id
+String name
+String description
+String image_path
+Boolean is_special
}
class InventoryItem {
+Integer id
+BigInteger player_id
+Integer drink_id
+String rarity
+Integer quantity
+relationship owner
+relationship drink
}
class ShopOffer {
+Integer id
+Integer offer_index
+Integer drink_id
+String rarity
+Integer batch_ts
+relationship drink
}
class AdminUser {
+BigInteger user_id
+String username
+Integer level
+Integer created_at
}
class PendingAddition {
+Integer id
+BigInteger proposer_id
+String name
+String description
+Boolean is_special
+String file_id
+String status
+Integer created_at
+BigInteger reviewed_by
+Integer reviewed_at
+String review_reason
}
class PendingDeletion {
+Integer id
+BigInteger proposer_id
+Integer drink_id
+String reason
+String status
+Integer created_at
+BigInteger reviewed_by
+Integer reviewed_at
+String review_reason
}
class PendingEdit {
+Integer id
+BigInteger proposer_id
+Integer drink_id
+String field
+String new_value
+String status
+Integer created_at
+BigInteger reviewed_by
+Integer reviewed_at
+String review_reason
}
class ModerationLog {
+Integer id
+Integer ts
+BigInteger actor_id
+String action
+Integer request_id
+BigInteger target_id
+String details
}
class GroupChat {
+BigInteger chat_id
+String title
+Boolean is_enabled
+Integer last_notified
}
class TgPremiumStock {
+Integer id
+Integer stock
}
class PurchaseReceipt {
+Integer id
+BigInteger user_id
+String kind
+Integer amount_coins
+Integer duration_seconds
+Integer purchased_at
+Integer valid_until
+String status
+BigInteger verified_by
+Integer verified_at
+String extra
}
class BonusStock {
+Integer id
+String kind
+Integer stock
}
class BoostHistory {
+Integer id
+BigInteger user_id
+String username
+String action
+Integer boost_count
+Integer boost_days
+BigInteger granted_by
+String granted_by_username
+Integer timestamp
+String details
}
Player "1" --> "*" InventoryItem : "has"
EnergyDrink "1" --> "*" InventoryItem : "contained in"
EnergyDrink "1" --> "*" ShopOffer : "available in"
Player "1" --> "*" PendingAddition : "proposes"
Player "1" --> "*" PendingDeletion : "requests"
Player "1" --> "*" PendingEdit : "submits"
AdminUser "1" --> "*" ModerationLog : "performs"
Player "1" --> "*" PurchaseReceipt : "purchases"
Player "1" --> "*" BoostHistory : "receives"
```

**Diagram sources**
- [database.py](file://database.py#L1-L100)

#### For API/Service Components:
```mermaid
sequenceDiagram
participant Service as "Business Logic"
participant DB as "database.py"
participant SQLite as "SQLite Database"
Service->>DB : get_or_create_player(user_id, username)
DB->>SQLite : SELECT * FROM players WHERE user_id = ?
alt Player exists
SQLite-->>DB : Return player record
DB-->>Service : Return Player object
else Player doesn't exist
SQLite-->>DB : No results
DB->>SQLite : INSERT INTO players (user_id, username) VALUES (?, ?)
DB->>SQLite : SELECT * FROM players WHERE user_id = ?
SQLite-->>DB : Return new player record
DB-->>Service : Return new Player object
end
Service->>DB : add_drink_to_inventory(user_id, drink_id, rarity)
DB->>SQLite : SELECT * FROM inventory_items WHERE player_id = ? AND drink_id = ? AND rarity = ?
alt Item exists
SQLite-->>DB : Return inventory item
DB->>SQLite : UPDATE inventory_items SET quantity = quantity + 1 WHERE id = ?
else Item doesn't exist
SQLite-->>DB : No results
DB->>SQLite : INSERT INTO inventory_items (player_id, drink_id, rarity, quantity) VALUES (?, ?, ?, 1)
end
DB->>SQLite : COMMIT
DB-->>Service : Success
Service->>DB : update_player(user_id, last_search=current_time, coins=new_coins)
DB->>SQLite : UPDATE players SET last_search = ?, coins = ? WHERE user_id = ?
DB->>SQLite : COMMIT
DB-->>Service : Success
```

**Diagram sources**
- [database.py](file://database.py#L1-L100)

**Section sources**
- [database.py](file://database.py#L1-L100)

### constants.py Analysis
The constants.py module serves as the central configuration point for the RELOAD application, containing global constants used throughout the system. This approach ensures consistency across the application and makes configuration changes easier to manage. The module defines game parameters, cooldown times, rarity distributions, pricing models, and administrative settings.

#### For Object-Oriented Components:
```mermaid
classDiagram
class constants {
+int SEARCH_COOLDOWN
+int DAILY_BONUS_COOLDOWN
+str ENERGY_IMAGES_DIR
+dict RARITIES
+dict COLOR_EMOJIS
+list RARITY_ORDER
+int ITEMS_PER_PAGE
+str VIP_EMOJI
+dict VIP_COSTS
+dict VIP_DURATIONS_SEC
+int TG_PREMIUM_COST
+int TG_PREMIUM_DURATION_SEC
+set ADMIN_USERNAMES
+int AUTO_SEARCH_DAILY_LIMIT
+float RECEIVER_COMMISSION
+dict RECEIVER_PRICES
+int SHOP_PRICE_MULTIPLIER
+dict SHOP_PRICES
}
```

**Diagram sources**
- [constants.py](file://constants.py#L1-L76)

**Section sources**
- [constants.py](file://constants.py#L1-L76)

## Dependency Analysis
The RELOAD application follows a clear dependency hierarchy with well-defined relationships between components. The main orchestrator (Bot_new.py) depends on all other modules, while specialized modules have minimal dependencies on each other. This design promotes modularity and makes the system easier to maintain and extend.

```mermaid
graph TD
Bot_new[Bot_new.py] --> database[database.py]
Bot_new --> constants[constants.py]
Bot_new --> admin[admin.py]
Bot_new --> admin2[admin2.py]
Bot_new --> fullhelp[fullhelp.py]
Bot_new --> add_energy[add_energy_drink_new.py]
admin[admin.py] --> database[database.py]
admin2[admin2.py] --> database[database.py]
fullhelp[fullhelp.py] --> database[database.py]
fullhelp --> constants[constants.py]
```

**Diagram sources**
- [Bot_new.py](file://Bot_new.py#L1-L100)
- [database.py](file://database.py#L1-L100)
- [constants.py](file://constants.py#L1-L76)
- [admin.py](file://admin.py#L1-L100)
- [admin2.py](file://admin2.py#L1-L100)
- [fullhelp.py](file://fullhelp.py#L1-L100)

## Performance Considerations
The RELOAD application is designed with performance in mind, leveraging asynchronous programming patterns to handle multiple concurrent users efficiently. The use of asyncio and the python-telegram-bot framework allows the bot to handle multiple user interactions simultaneously without blocking. Database operations are optimized through the use of SQLAlchemy ORM with appropriate indexing on frequently queried fields. The system implements caching patterns where appropriate, such as maintaining player state in memory during active sessions. The repository pattern in database.py provides a clean abstraction that allows for future optimization of data access patterns without affecting business logic.

## Troubleshooting Guide
When troubleshooting issues with the RELOAD application, consider the following common scenarios and their solutions:

1. **Database Connection Issues**: Ensure the SQLite database file (bot_data.db) exists and has proper read/write permissions. The database is created automatically on first run if it doesn't exist.

2. **Command Not Responding**: Check if the bot has been granted necessary permissions in the Telegram group or channel. Verify that the python-telegram-bot library is properly installed and configured.

3. **Authentication Problems**: Ensure that admin users are properly registered in the database. The bootstrap admin usernames are defined in constants.py under ADMIN_USERNAMES.

4. **Image Display Issues**: Verify that the energy_images directory exists and contains the required image files. Check that the image paths in the database match the actual file locations.

5. **Asynchronous Operation Failures**: Review the asyncio event loop configuration and ensure that long-running operations are properly awaited. Check for potential race conditions in shared state.

6. **Memory Leaks**: Monitor the application for increasing memory usage over time. The use of global dictionaries (PENDING_ADDITIONS, GIFT_OFFERS, _LOCKS, REJECT_PROMPTS) should be periodically cleaned up to prevent memory bloat.

**Section sources**
- [Bot_new.py](file://Bot_new.py#L1-L100)
- [database.py](file://database.py#L1-L100)

## Conclusion
The RELOAD application demonstrates a well-architected modular design with clear separation of concerns between presentation, business logic, data access, and configuration layers. The system leverages asynchronous programming patterns through asyncio and the python-telegram-bot framework to efficiently handle concurrent user interactions. The use of the Repository pattern in database.py provides a clean abstraction between business logic and data storage, enhancing maintainability and testability. Key design decisions such as the use of global constants, singleton-like patterns in database session management, and state handling via callback data contribute to the system's robustness and scalability. The architecture supports easy extension through its modular design, allowing new features to be added with minimal impact on existing functionality.