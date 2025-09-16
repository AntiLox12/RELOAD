# VIP System

<cite>
**Referenced Files in This Document**   
- [Bot_new.py](file://Bot_new.py)
- [database.py](file://database.py)
- [constants.py](file://constants.py)
</cite>

## Table of Contents
1. [VIP Subscription Management](#vip-subscription-management)
2. [Benefit Calculation and Game Mechanics](#benefit-calculation-and-game-mechanics)
3. [Auto-Search Functionality](#auto-search-functionality)
4. [VIP Status Storage and Validation](#vip-status-storage-and-validation)
5. [Economic and Administrative Integration](#economic-and-administrative-integration)
6. [Common Issues and Solutions](#common-issues-and-solutions)

## VIP Subscription Management

The VIP subscription system allows players to purchase temporary VIP status through in-game purchases. The system supports three subscription tiers defined in `constants.py`: 1-day (500 coins), 7-day (3,000 coins), and 30-day (10,000 coins). Players initiate purchases through dedicated menu options that display pricing and current VIP expiration status.

The purchase process is handled by the `buy_vip` function in `Bot_new.py`, which validates the selected plan and checks player coin balance before proceeding. A locking mechanism prevents double-click exploits during the transaction. The actual coin deduction and VIP duration extension is managed by the `purchase_vip` function in `database.py`, which calculates the new expiration timestamp by adding the purchased duration to either the current time (if no active VIP exists) or the remaining VIP time (if extending an active subscription).

Administrative commands in `admin2.py` provide manual VIP management capabilities. The `/addvip` command allows privileged administrators to grant VIP status to individual users or all players, specifying the duration in days. This administrative functionality bypasses the economic system and is restricted to level 3 administrators and the Creator role.

**Section sources**
- [Bot_new.py](file://Bot_new.py#L1244-L1277)
- [database.py](file://database.py#L2517-L2539)
- [admin2.py](file://admin2.py#L374-L456)
- [constants.py](file://constants.py#L30-L38)

## Benefit Calculation and Game Mechanics

VIP status provides multiple gameplay advantages that are implemented through conditional logic in the game's core mechanics. The primary benefits include reduced cooldowns, increased rewards, and special interface indicators. These benefits are activated whenever a player's VIP status is validated through the `is_vip` function in `database.py`.

The cooldown reduction is implemented by applying a 0.5 multiplier to both search and daily bonus cooldowns. In `Bot_new.py`, the effective cooldown is calculated as `SEARCH_COOLDOWN / 2` for VIP players, reducing the standard 5-minute (300-second) cooldown to 2.5 minutes. Similarly, the daily bonus cooldown is halved from 24 hours to 12 hours for VIP players.

Reward enhancement is implemented in the `_perform_energy_search` function, where VIP players receive double the standard coin reward (5-10 coins) for successful searches, resulting in 10-20 coins. This calculation occurs within the search logic, where the base reward is conditionally multiplied by 2 when `vip_active` evaluates to true.

The VIP status is visually represented through the `VIP_EMOJI` (👑) which appears in various interfaces, including search results and the VIP status display. The VIP indicator is conditionally added to messages when the player's `vip_until` timestamp is greater than the current time.

**Section sources**
- [Bot_new.py](file://Bot_new.py#L361-L393)
- [Bot_new.py](file://Bot_new.py#L426-L447)
- [Bot_new.py](file://Bot_new.py#L628-L652)
- [constants.py](file://constants.py#L20-L21)

## Auto-Search Functionality

The auto-search feature is an exclusive VIP benefit that automatically performs energy drink searches on behalf of the player at regular intervals. This functionality is implemented as a scheduled job in the Telegram bot's JobQueue system, with the `auto_search_job` function serving as the primary execution handler.

When a player enables auto-search through the settings menu, the system first verifies VIP status before activating the feature. The job scheduler is then initialized with a 1-second delay to trigger the first search attempt. Subsequent searches are scheduled based on the effective search cooldown, which is halved for VIP players (150 seconds instead of 300 seconds).

The system implements a daily usage limit of 60 searches, defined by the `AUTO_SEARCH_DAILY_LIMIT` constant. A daily counter (`auto_search_count`) and reset timestamp (`auto_search_reset_ts`) are stored in the Player model and automatically reset every 24 hours. When the daily limit is reached, the auto-search feature is automatically disabled and the player is notified.

To prevent race conditions, the auto-search system uses locking mechanisms that coordinate with manual search operations. If a manual search is in progress when an auto-search job triggers, the job is rescheduled for 5 seconds later. The system also handles edge cases such as empty energy drink inventory by notifying the player and rescheduling the job for 10 minutes later.

**Section sources**
- [Bot_new.py](file://Bot_new.py#L3136-L3183)
- [Bot_new.py](file://Bot_new.py#L395-L424)
- [Bot_new.py](file://Bot_new.py#L449-L488)
- [constants.py](file://constants.py#L46)

## VIP Status Storage and Validation

VIP status is stored in the Player model as a timestamp field named `vip_until`, which represents the Unix timestamp when the VIP status expires. This approach allows for efficient validation by comparing the current time with the stored expiration timestamp. The Player model also includes several related fields for auto-search functionality, including `auto_search_enabled`, `auto_search_count`, and `auto_search_reset_ts`.

The primary validation function is `is_vip` in `database.py`, which returns true if the current time is less than the `vip_until` timestamp. This simple comparison enables efficient status checks throughout the application. The `get_vip_until` function provides direct access to the expiration timestamp for display purposes.

Status validation occurs in multiple contexts throughout the application. In `Bot_new.py`, the `show_menu` function checks VIP status to determine which cooldown values to display for search and daily bonus actions. The `auto_search_job` function performs VIP validation at the beginning of each execution cycle and automatically disables the feature if the VIP status has expired.

The system also includes mechanisms for handling expired subscriptions. When a VIP subscription expires, the `auto_search_job` function detects this condition, disables the auto-search feature, and sends a notification to the player. This ensures that premium benefits are automatically revoked when the subscription period ends.

**Section sources**
- [database.py](file://database.py#L2277-L2300)
- [database.py](file://database.py#L2517-L2539)
- [Bot_new.py](file://Bot_new.py#L361-L393)
- [Bot_new.py](file://Bot_new.py#L449-L488)

## Economic and Administrative Integration

The VIP system is integrated with the game's economic model through the coin-based purchase system. Players must spend in-game currency (septims) to acquire VIP status, with prices defined in the `VIP_COSTS` dictionary in `constants.py`. The purchase transaction deducts coins from the player's balance and is processed through the `purchase_vip` function, which ensures atomicity through database transactions.

The system is also integrated with administrative controls through the `/addvip` command in `admin2.py`. This command allows privileged users to grant VIP status without requiring coin payment, providing a mechanism for promotions, rewards, or testing. The administrative system can target individual users by username or apply VIP status to all players simultaneously.

The VIP menu interface in `Bot_new.py` integrates with the game's localization system, displaying prices, status information, and purchase options in the player's selected language. The interface also displays the player's current coin balance and indicates insufficient funds when the player cannot afford a VIP purchase.

The system includes integration with the auto-search boost functionality, which allows administrators to grant additional daily search limits through the `/addautosearch` command. This creates a tiered premium experience where VIP status provides the base auto-search capability, while additional boosts provide enhanced usage limits.

**Section sources**
- [Bot_new.py](file://Bot_new.py#L1526-L1549)
- [Bot_new.py](file://Bot_new.py#L1598-L1617)
- [admin2.py](file://admin2.py#L374-L456)
- [constants.py](file://constants.py#L30-L38)

## Common Issues and Solutions

A common issue in the VIP system is the failure to detect expired subscriptions, which could allow players to retain premium benefits after their subscription has ended. This is addressed through proactive validation in the `auto_search_job` function, which checks VIP status at the beginning of each execution cycle and automatically disables auto-search functionality when the VIP status has expired.

Another potential issue is race conditions during VIP purchases, where multiple purchase attempts could lead to inconsistent state or coin balance errors. This is mitigated through the use of asyncio locks in the `buy_vip` function, which prevents concurrent purchase operations for the same user. The database operations are also wrapped in transactions with row-level locking to ensure data consistency.

Timestamp validation issues are prevented by using Unix timestamps (seconds since epoch) for all time calculations, ensuring consistent time representation across different systems and time zones. The system uses `time.time()` for current time retrieval and `time.strftime()` for display formatting, with all comparisons performed using numeric timestamp values.

Database schema evolution is handled through migration logic that checks for the existence of VIP-related columns and adds them if missing. This ensures backward compatibility when deploying the VIP system to existing databases. The system also includes error handling for cases where player records do not exist, automatically creating player entries when necessary to prevent transaction failures.

**Section sources**
- [Bot_new.py](file://Bot_new.py#L449-L488)
- [Bot_new.py](file://Bot_new.py#L1244-L1277)
- [database.py](file://database.py#L2277-L2300)
- [Bot_new.py](file://Bot_new.py#L3136-L3183)