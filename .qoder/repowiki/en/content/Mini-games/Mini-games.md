# Mini-games

<cite>
**Referenced Files in This Document**   
- [Bot_new.py](file://Bot_new.py)
- [database.py](file://database.py)
- [constants.py](file://constants.py)
</cite>

## Table of Contents
1. [Casino Gambling Mechanics](#casino-gambling-mechanics)
2. [Plantation Farming System](#plantation-farming-system)
3. [Daily Bonus System](#daily-bonus-system)
4. [Game State Persistence](#game-state-persistence)
5. [Economic System Integration](#economic-system-integration)
6. [VIP Benefits](#vip-benefits)
7. [Randomization and Fairness](#randomization-and-fairness)

## Casino Gambling Mechanics

The casino gambling mechanics are implemented through the search functionality in the bot, where players search for energy drinks with randomized outcomes. The win/loss probability is determined by the rarity distribution system defined in the constants. Each search action represents a gambling event where players have varying probabilities of obtaining different rarity items.

The core probability model uses weighted random selection based on predefined rarity weights. The `RARITIES` dictionary in `constants.py` defines the probability distribution: Basic (50), Medium (30), Elite (15), Absolute (4), and Majestic (1). These values represent relative weights rather than percentages, with higher values indicating greater likelihood of occurrence. The actual probability calculation uses Python's `random.choices()` function with these weights to determine the rarity of found items.

When a player performs a search, the system first checks cooldown restrictions, then selects a random energy drink from the available pool. The rarity is determined through weighted random selection using the RARITIES weights. Special items have fixed probability as they bypass the weighted system when `is_special` flag is set. The outcome is immediately reflected in the player's inventory and communicated through the interface with appropriate visual feedback.

**Section sources**
- [Bot_new.py](file://Bot_new.py#L490-L516)
- [constants.py](file://constants.py#L25-L32)

## Plantation Farming System

The plantation farming system implements a time-based cultivation mechanic where players can grow energy drink seeds to harvest multiple items. The system is built around several key components: seed types, plantation beds, fertilizers, and growth cycles. Each seed type has specific growth parameters including `grow_time_sec`, `water_interval_sec`, `yield_min`, and `yield_max` that define its cultivation characteristics.

Players interact with the plantation through dedicated command handlers that allow planting seeds, watering crops, applying fertilizers, and harvesting mature plants. The growth cycle is entirely time-dependent, with the system calculating whether a plant has reached maturity by comparing the current timestamp with the `planted_at` timestamp. The base growth duration is defined by each seed type's `grow_time_sec` parameter.

The system incorporates several gameplay mechanics to enhance the farming experience. Watering the plant increments a `water_count` that contributes to yield multipliers (up to +25% for five waterings). Fertilizers provide temporary bonuses that enhance growth or yield, with effects lasting for a specified duration. Negative status effects like weeds, pests, or drought can reduce harvest quality. The final yield amount is calculated using random selection between the seed's `yield_min` and `yield_max` values, modified by various bonuses and penalties.

**Section sources**
- [database.py](file://database.py#L204-L280)
- [database.py](file://database.py#L1398-L1436)

## Daily Bonus System

The daily bonus system provides players with a regular reward mechanism that encourages consistent engagement. Players can claim a daily bonus that awards them with a random energy drink from the available pool. The system implements a cooldown mechanism that prevents frequent claiming, with the default interval set to 86,400 seconds (24 hours) as defined in `DAILY_BONUS_COOLDOWN`.

The bonus claiming process follows a standard pattern: first, the system verifies that sufficient time has elapsed since the last claim by comparing the current timestamp with `last_bonus_claim`. If the cooldown period has passed, the system selects a random energy drink and determines its rarity using the same weighted probability system as the search functionality. The selected item is then added to the player's inventory, and the `last_bonus_claim` timestamp is updated to the current time.

The interface provides visual feedback about the remaining cooldown time, displaying it in hours, minutes, and seconds format. This countdown creates anticipation and encourages players to return when the bonus becomes available. The system also includes anti-abuse measures such as locking mechanisms to prevent double claims and ensure atomic operations during the claiming process.

**Section sources**
- [Bot_new.py](file://Bot_new.py#L628-L686)
- [constants.py](file://constants.py#L18-L19)

## Game State Persistence

Game states for all mini-games are persisted through the database models defined in `database.py`, with the `Player` model serving as the central entity for storing user-specific game states. The SQLAlchemy ORM framework is used to manage the object-relational mapping, with SQLite as the underlying database engine. All game state data is stored in a single database file named `bot_data.db`.

For the plantation system, multiple related models handle the persistence: `PlantationBed` tracks the state of each individual bed (empty, growing, ready, withered), `SeedType` defines the characteristics of cultivable seeds, and `SeedInventory` manages the player's seed stock. The `PlantationBed` model includes timestamp fields like `planted_at` and `last_watered_at` that are crucial for time-based calculations in the farming mechanics.

The daily bonus system relies on the `last_bonus_claim` field in the `Player` model to track when a player last claimed their bonus. Similarly, the search functionality uses `last_search` to enforce cooldown periods. These timestamp fields are stored as integers representing Unix time, enabling straightforward time difference calculations. The database operations are wrapped in transaction-safe methods that use row-level locking to prevent race conditions during concurrent access.

**Section sources**
- [database.py](file://database.py#L17-L46)
- [database.py](file://database.py#L258-L280)

## Economic System Integration

The mini-games are tightly integrated with the bot's economic system, where winnings and losses directly affect the player's coin balance. The search functionality rewards players with 5-10 coins per successful search, with VIP players receiving double rewards. These coins are added to the player's balance stored in the `coins` field of the `Player` model and can be used for various in-game purchases.

The plantation system contributes to the economy by enabling players to generate multiple inventory items from a single seed purchase. This amplification mechanic encourages investment in seeds and fertilizers, creating a production-based economy. When players sell harvested items through the receiver system, they receive coins based on the item's rarity, with different payout rates for each rarity tier as defined in `RECEIVER_PRICES`.

The daily bonus system injects new items into the economy without direct coin expenditure, serving as a reward mechanism that increases the overall item circulation. The economic balance is maintained through carefully calibrated prices and rewards, with seed costs, fertilizer prices, and sale values creating a sustainable loop. The system also includes community plantations that introduce cooperative economic elements, where player contributions to communal projects are rewarded from a shared coin pool.

**Section sources**
- [Bot_new.py](file://Bot_new.py#L500-L505)
- [database.py](file://database.py#L2763-L2808)
- [constants.py](file://constants.py#L55-L62)

## VIP Benefits

VIP status provides enhanced benefits across all mini-games, creating a premium experience that incentivizes players to purchase VIP subscriptions. The VIP system is implemented through timestamp-based tracking with the `vip_until` field in the `Player` model, which stores the expiration time of the VIP status. Various game mechanics check this status to determine if VIP benefits should be applied.

In the search functionality, VIP players enjoy a 50% reduction in cooldown time, allowing them to search more frequently. They also receive double coin rewards from each search, effectively doubling their income from this activity. The daily bonus system similarly reduces the cooldown by 50% for VIP players, enabling more frequent bonus claims. These time-based advantages significantly increase the rate at which VIP players can accumulate resources.

The VIP auto-search feature provides an additional layer of convenience, automatically performing searches on behalf of the player up to a daily limit. This passive income mechanism allows VIP players to accumulate items and coins without active participation. The system uses JobQueue to schedule periodic search operations, respecting both the cooldown mechanics and daily limits. These compounded advantages create a substantial gameplay differential between VIP and non-VIP players.

**Section sources**
- [Bot_new.py](file://Bot_new.py#L262-L280)
- [constants.py](file://constants.py#L40-L47)

## Randomization and Fairness

The mini-games employ Python's `random` module for outcome determination, with various mechanisms to ensure fairness and unpredictability. The primary randomization occurs in the search and bonus systems, where `random.choice()` selects items from the available pool and `random.choices()` with weights determines item rarities. This weighted selection system ensures that rarer items appear less frequently according to the probability distribution defined in constants.

To address potential issues with predictable gambling outcomes, the system could be enhanced with cryptographically secure random number generation. Currently, the standard `random` module uses a deterministic algorithm that could theoretically be predicted. Implementing `secrets.SystemRandom` or similar cryptographically secure generators would improve fairness by using system entropy sources. The code already imports the `secrets` module, indicating awareness of security considerations.

The plantation yield system incorporates randomness through the range between `yield_min` and `yield_max`, creating variable returns that keep the gameplay engaging. This randomness is balanced by skill-based elements like timely watering and strategic fertilizer use, which influence the final outcome. The combination of random and deterministic factors creates a gameplay experience that rewards both luck and player engagement.

**Section sources**
- [Bot_new.py](file://Bot_new.py#L490-L516)
- [constants.py](file://constants.py#L25-L32)