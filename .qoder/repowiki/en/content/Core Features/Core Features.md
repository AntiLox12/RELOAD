# Core Features

<cite>
**Referenced Files in This Document**   
- [Bot_new.py](file://Bot_new.py)
- [database.py](file://database.py)
- [constants.py](file://constants.py)
</cite>

## Table of Contents
1. [Energy Drink Collection System](#energy-drink-collection-system)
2. [Inventory Management](#inventory-management)
3. [Search Command Implementation](#search-command-implementation)
4. [Integration with VIP System and Economic Model](#integration-with-vip-system-and-economic-model)
5. [Concurrency and Race Condition Handling](#concurrency-and-race-condition-handling)

## Energy Drink Collection System

The RELOAD bot implements a cooldown-based energy drink collection system that governs how frequently users can search for new items. The core mechanic is defined by the `SEARCH_COOLDOWN` constant in `constants.py`, which sets the base cooldown period at 300 seconds (5 minutes). This value is dynamically adjusted for VIP users, who benefit from a 50% reduced cooldown due to their subscription status.

When a user initiates a search via the `/find` command or the "Find energy" button, the system first checks whether the user is within their cooldown period by comparing the current time with the `last_search` timestamp stored in the database. If the cooldown has not expired, the request is rejected with an appropriate message. For VIP users, the effective cooldown (`eff_search_cd`) is calculated as `SEARCH_COOLDOWN / 2`, providing a significant gameplay advantage.

Upon successful cooldown validation, the system selects a random energy drink from the available pool using `db.get_all_drinks()`. The rarity of the found item is determined through a weighted random selection based on the `RARITIES` dictionary, where rarer items have lower probability weights. Special items bypass this system and are automatically assigned the 'Special' rarity.

Users are rewarded with a random amount of septims (5-10 coins) upon finding an energy drink, with VIP users receiving double the reward. This economic incentive encourages regular engagement with the collection system. The entire process is logged for monitoring and analytics purposes, capturing details such as user ID, found item, rarity, and coin rewards.

**Section sources**
- [Bot_new.py](file://Bot_new.py#L490-L539)
- [constants.py](file://constants.py#L5-L7)

## Inventory Management

The inventory management system implements both pagination and rarity-based sorting to provide an organized and user-friendly interface for viewing collected energy drinks. The inventory display is accessible through the "Inventory" button in the main menu and shows items across multiple pages when necessary.

Pagination is controlled by the `ITEMS_PER_PAGE` constant, which is set to 10 items per page. When displaying the inventory, the system calculates the total number of pages based on the user's inventory size and implements navigation buttons (previous, next) to allow users to browse through their collection. The current page number and total page count are displayed to provide context.

Items are sorted according to a predefined rarity hierarchy specified in `RARITY_ORDER`, which ranks items from most to least valuable: Special, Majestic, Absolute, Elite, Medium, Basic. Within each rarity tier, items are further sorted alphabetically by name. This dual-sorting mechanism ensures a consistent and logical presentation of the user's collection.

The interface groups items by rarity, displaying a header for each rarity tier with its corresponding emoji indicator from `COLOR_EMOJIS`. Each item is presented with its name and quantity, allowing users to quickly assess their collection composition. Navigation is intuitive, with dedicated buttons for moving between pages and returning to the main menu.

**Section sources**
- [Bot_new.py](file://Bot_new.py#L730-L790)
- [constants.py](file://constants.py#L15-L16)

## Search Command Implementation

The `/find` command serves as the primary interface for energy drink collection, triggering a comprehensive sequence of operations across multiple components. When invoked, the command first acquires a user-specific lock (`_get_lock(f"user:{user.id}:search")`) to prevent concurrent searches and potential race conditions.

The command handler performs an initial cooldown check using the user's `last_search` timestamp and the current `SEARCH_COOLDOWN` value, adjusted for VIP status. If the cooldown period has not elapsed, the user receives a notification with the remaining time. Upon passing the cooldown check, the system displays a loading animation with rotating search indicators to provide visual feedback during processing.

The core search logic is encapsulated in the `_perform_energy_search` function, which coordinates the selection of a random energy drink, determination of its rarity, updating of the user's inventory, and calculation of coin rewards. The selected drink is added to the user's inventory via `db.add_drink_to_inventory`, while the user's coin balance is updated through `db.update_player` with the appropriate reward amount.

For successful searches, the system generates a detailed response message that includes the drink's name, rarity (with emoji indicator), reward amount, and description. If the drink has an associated image, it is displayed alongside the text. The user's `last_search` timestamp is updated to enforce the cooldown period for future searches.

```mermaid
sequenceDiagram
participant User
participant Bot_new
participant Database
participant Constants
User->>Bot_new : /find command
Bot_new->>Bot_new : Acquire search lock
Bot_new->>Database : Check last_search timestamp
alt Cooldown active
Bot_new-->>User : "Wait, cooldown active"
else Cooldown expired
Bot_new->>Bot_new : Show loading animation
Bot_new->>Database : Get all drinks
Bot_new->>Bot_new : Select random drink
Bot_new->>Bot_new : Determine rarity (weighted)
Bot_new->>Database : Add to inventory
Bot_new->>Bot_new : Calculate coin reward
Bot_new->>Database : Update player (coins, last_search)
Bot_new->>User : Display found item with details
end
Bot_new->>Bot_new : Release search lock
```

**Diagram sources**
- [Bot_new.py](file://Bot_new.py#L563-L598)
- [database.py](file://database.py#L2044-L2074)

**Section sources**
- [Bot_new.py](file://Bot_new.py#L3353-L3386)
- [Bot_new.py](file://Bot_new.py#L490-L539)

## Integration with VIP System and Economic Model

The energy drink collection system is deeply integrated with the VIP subscription system and broader economic model of the RELOAD bot. VIP status, determined by `db.is_vip(user.id)`, provides multiple advantages that enhance the user experience and create a compelling value proposition for subscription.

VIP users benefit from a 50% reduction in both the search cooldown (`SEARCH_COOLDOWN / 2`) and daily bonus cooldown (`DAILY_BONUS_COOLDOWN / 2`), allowing them to collect rewards more frequently. Additionally, they receive double the coin rewards from searches, significantly accelerating their accumulation of in-game currency. These multiplier effects create a positive feedback loop where VIP status enables faster progression and greater earning potential.

The economic model is further reinforced through the autosearch feature, which allows VIP users to automatically perform searches up to a daily limit (`AUTO_SEARCH_DAILY_LIMIT`). This passive income mechanism operates through scheduled jobs in the Telegram bot framework, with the system automatically triggering searches at appropriate intervals. The autosearch functionality respects the same cooldown mechanics as manual searches but operates in the background, providing continuous rewards without requiring active user participation.

The system also integrates with the marketplace economy through defined pricing structures. The `RECEIVER_PRICES` dictionary establishes base values for selling energy drinks, while `SHOP_PRICES` determines purchase costs with a multiplier applied. This creates a balanced economy where users can buy and sell items at predictable rates, with the `RECEIVER_COMMISSION` ensuring the system retains a percentage of transaction value.

**Section sources**
- [constants.py](file://constants.py#L20-L37)
- [Bot_new.py](file://Bot_new.py#L361-L393)
- [database.py](file://database.py#L1629-L1668)

## Concurrency and Race Condition Handling

The RELOAD bot implements robust mechanisms to prevent race conditions and ensure data consistency during concurrent operations, particularly for critical actions like searching and inventory management. The primary defense against race conditions is the use of asyncio locks, with each user having a dedicated search lock identified by `f"user:{user.id}:search"`.

When a user initiates a search, the system first checks if the lock is already acquired. If so, the request is immediately rejected with a "Search already in progress" message, preventing multiple simultaneous searches that could lead to inconsistent state or unfair advantages. This locking mechanism is applied consistently across all search entry points, including the `/find` command, button presses, and autosearch jobs.

For database operations, the system employs transactional integrity through SQLAlchemy's session management. Operations that modify multiple related records, such as adding an item to inventory and updating player statistics, are wrapped in atomic transactions. If any part of the operation fails, the entire transaction is rolled back, ensuring that the database remains in a consistent state.

The autosearch system includes additional safeguards to prevent conflicts with manual searches. Before executing an autosearch job, the system checks if the user's search lock is held, indicating an ongoing manual search. If a conflict is detected, the autosearch is rescheduled for a short delay, allowing the manual search to complete first. This coordination ensures that users cannot exploit timing differences between automated and manual actions.

```mermaid
flowchart TD
Start([Search Initiated]) --> CheckLock["Check user search lock"]
CheckLock --> LockHeld{"Lock Held?"}
LockHeld --> |Yes| Reject["Reject: Search in progress"]
LockHeld --> |No| AcquireLock["Acquire lock"]
AcquireLock --> CheckCooldown["Check cooldown period"]
CheckCooldown --> CooldownActive{"Cooldown Active?"}
CooldownActive --> |Yes| NotifyCooldown["Notify: Wait for cooldown"]
CooldownActive --> |No| PerformSearch["Perform search logic"]
PerformSearch --> UpdateDB["Update database (atomic)"]
UpdateDB --> ReleaseLock["Release lock"]
ReleaseLock --> End([Search Complete])
Reject --> End
NotifyCooldown --> End
```

**Diagram sources**
- [Bot_new.py](file://Bot_new.py#L563-L598)
- [Bot_new.py](file://Bot_new.py#L361-L393)

**Section sources**
- [Bot_new.py](file://Bot_new.py#L311-L329)
- [database.py](file://database.py#L2044-L2074)