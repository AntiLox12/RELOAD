# Database Schema Design

<cite>
**Referenced Files in This Document**   
- [database.py](file://database.py) - *Updated in recent commit*
- [silk_city.py](file://silk_city.py) - *Added in recent commit*
- [constants.py](file://constants.py) - *Updated in recent commit*
</cite>

## Update Summary
**Changes Made**   
- Added documentation for new Silk City features including plantations, inventory, and transactions
- Updated Entity-Relationship Diagram to include new entities and relationships
- Added new sections for SilkPlantation, SilkInventory, and SilkTransaction models
- Updated Business Rules section to include silk plantation mechanics and VIP bonuses
- Added new sample queries for silk-related data access patterns
- Updated indexing and performance optimization section with new indexes

## Table of Contents
1. [Introduction](#introduction)
2. [Entity-Relationship Diagram](#entity-relationship-diagram)
3. [Core Data Models](#core-data-models)
4. [Business Rules and Game Mechanics](#business-rules-and-game-mechanics)
5. [Data Access Patterns and Sample Queries](#data-access-patterns-and-sample-queries)
6. [Data Validation and Constraints](#data-validation-and-constraints)
7. [Indexing and Performance Optimization](#indexing-and-performance-optimization)
8. [Transaction Management](#transaction-management)
9. [Data Lifecycle and Migration](#data-lifecycle-and-migration)
10. [Conclusion](#conclusion)

## Introduction

This document provides comprehensive documentation for the database schema of the RELOAD application, a Telegram bot for collecting energy drinks. The schema is designed to support core gameplay mechanics including player progression, inventory management, shop systems, and administrative moderation. The database is implemented using SQLite with SQLAlchemy ORM, featuring a normalized structure to ensure data integrity and efficient querying.

The primary entities include Player, EnergyDrink, InventoryItem, AdminUser, PendingAddition, and ShopOffer, which form the backbone of the application's data model. These entities are interconnected through well-defined relationships that support the game's business logic, such as how player status affects collection rates and how rarity levels influence inventory sorting. The schema also includes supporting entities for moderation workflows, transaction logging, and system operations.

This documentation details the field definitions, data types, primary and foreign keys, constraints, and indexes for each table. It explains the business rules governing entity interactions, provides sample queries for common access patterns, and outlines data validation rules and performance optimization strategies. The document also covers transaction management patterns, data lifecycle policies, and considerations for future schema migrations.

**Section sources**
- [database.py](file://database.py#L1-L100)

## Entity-Relationship Diagram

```mermaid
erDiagram
PLAYER ||--o{ INVENTORY_ITEM : owns
PLAYER ||--o{ PENDING_ADDITION : proposes
PLAYER ||--o{ PENDING_DELETION : proposes
PLAYER ||--o{ PENDING_EDIT : proposes
PLAYER ||--o{ MODERATION_LOG : performs
PLAYER ||--o{ BOOST_HISTORY : has
PLAYER ||--o{ PURCHASE_RECEIPT : makes
PLAYER ||--o{ COMMUNITY_PARTICIPANT : joins
PLAYER ||--o{ SEED_INVENTORY : holds
PLAYER ||--o{ FERTILIZER_INVENTORY : holds
PLAYER ||--o{ PLANTATION_BED : owns
PLAYER ||--o{ SILK_PLANTATION : owns
PLAYER ||--o{ SILK_INVENTORY : holds
ENERGY_DRINK ||--o{ INVENTORY_ITEM : has
ENERGY_DRINK ||--o{ SHOP_OFFER : available_as
ENERGY_DRINK ||--o{ PENDING_ADDITION : proposed
ENERGY_DRINK ||--o{ PENDING_DELETION : targeted
ENERGY_DRINK ||--o{ PENDING_EDIT : targeted
ENERGY_DRINK ||--o{ SEED_TYPE : grown_from
ADMIN_USER ||--o{ MODERATION_LOG : performs
ADMIN_USER ||--o{ PENDING_ADDITION : reviews
ADMIN_USER ||--o{ PENDING_DELETION : reviews
ADMIN_USER ||--o{ PENDING_EDIT : reviews
ADMIN_USER ||--o{ BOOST_HISTORY : grants
COMMUNITY_PLANTATION ||--o{ COMMUNITY_PROJECT_STATE : has
COMMUNITY_PLANTATION ||--o{ COMMUNITY_PARTICIPANT : has
COMMUNITY_PLANTATION ||--o{ COMMUNITY_CONTRIB_LOG : has
SEED_TYPE ||--o{ SEED_INVENTORY : stocked_as
SEED_TYPE ||--o{ PLANTATION_BED : planted_as
FERTILIZER ||--o{ FERTILIZER_INVENTORY : stocked_as
FERTILIZER ||--o{ PLANTATION_BED : applied_as
SILK_PLANTATION ||--o{ SILK_TRANSACTION : generates
SILK_INVENTORY ||--o{ SILK_TRANSACTION : involved_in
PLAYER {
bigint user_id PK
string username
int coins
int last_search
int last_bonus_claim
int last_add
string language
bool remind
int vip_until
int tg_premium_until
bool auto_search_enabled
int auto_search_count
int auto_search_reset_ts
int auto_search_boost_count
int auto_search_boost_until
}
ENERGY_DRINK {
int id PK
string name UK
string description
string image_path
bool is_special
}
INVENTORY_ITEM {
int id PK
bigint player_id FK
int drink_id FK
string rarity
int quantity
}
ADMIN_USER {
bigint user_id PK
string username
int level
int created_at
}
PENDING_ADDITION {
int id PK
bigint proposer_id
string name
string description
bool is_special
string file_id
string status
int created_at
bigint reviewed_by
int reviewed_at
string review_reason
}
SHOP_OFFER {
int id PK
int offer_index
int drink_id FK
string rarity
int batch_ts
}
SILK_PLANTATION {
int id PK
bigint player_id FK
string plantation_name
int silk_trees_count
int planted_at
int harvest_ready_at
string status
int investment_cost
int expected_yield
string investment_level
int quality_modifier
int weather_modifier
}
SILK_INVENTORY {
int id PK
bigint player_id FK
string silk_type
int quantity
int quality_grade
int produced_at
}
SILK_TRANSACTION {
int id PK
bigint seller_id FK
bigint buyer_id FK
string transaction_type
string silk_type
int amount
int price_per_unit
int total_price
int created_at
}
```

**Diagram sources**
- [database.py](file://database.py#L206-L267) - *Added silk city models*

## Core Data Models

### Player Model
The Player model represents a Telegram user participating in the game. Each player is uniquely identified by their user_id, which corresponds to their Telegram ID. The model tracks various gameplay metrics including coin balance, cooldown timers for actions like searching and claiming daily bonuses, and player preferences such as language and reminder settings.

VIP status is managed through the vip_until field, which stores a Unix timestamp indicating when the VIP status expires. The model also supports an auto-search feature with fields to track enabled status, daily search count, reset timestamp, and boost information. The relationship with InventoryItem establishes a one-to-many association, allowing players to own multiple inventory items.

**Section sources**
- [database.py](file://database.py#L19-L38)

### EnergyDrink Model
The EnergyDrink model defines the catalog of collectible energy drinks in the game. Each drink has a unique name, description, and optional image path. The is_special flag indicates whether the drink belongs to a special category. The model serves as the reference point for all drink-related operations, including inventory management, shop offerings, and moderation requests.

Drinks are referenced by other entities through their primary key ID, establishing foreign key relationships with InventoryItem, ShopOffer, and various moderation entities. The unique constraint on the name field ensures that no two drinks can have identical names, maintaining data integrity across the application.

**Section sources**
- [database.py](file://database.py#L40-L46)

### InventoryItem Model
The InventoryItem model represents a player's collection of energy drinks. Each inventory item is associated with a specific player and drink, with the rarity field indicating the quality tier of the collected item. The quantity field tracks how many copies of the same drink and rarity combination the player possesses.

The model includes indexes on player_id, drink_id, and rarity to optimize query performance for common operations like retrieving a player's inventory or counting specific items. The relationship with Player and EnergyDrink enables efficient navigation between entities, allowing the application to display comprehensive inventory information with minimal database queries.

**Section sources**
- [database.py](file://database.py#L48-L62)

### AdminUser Model
The AdminUser model manages administrative privileges within the application. Each admin is identified by their Telegram user_id and has a level field that determines their permissions (1=Junior Moderator, 2=Senior Moderator, 3=Head Admin). The created_at field records when the admin account was created.

This model enables role-based access control, allowing different levels of administrative functionality. Admins can perform moderation tasks such as reviewing pending additions, deletions, and edits, with their actions logged in the ModerationLog table. The relationship with moderation entities ensures accountability and auditability of administrative actions.

**Section sources**
- [database.py](file://database.py#L78-L83)

### PendingAddition Model
The PendingAddition model handles user-submitted requests to add new energy drinks to the game. Each pending addition includes the proposer's ID, proposed drink details (name, description, special status), and file ID for the drink image. The status field tracks the review progress (pending/approved/rejected).

The model supports a moderation workflow where admins can review and approve or reject submissions. The reviewed_by and reviewed_at fields record which admin processed the request and when, while review_reason stores any comments. This entity enables community-driven content expansion while maintaining quality control through administrative oversight.

**Section sources**
- [database.py](file://database.py#L87-L99)

### ShopOffer Model
The ShopOffer model implements the in-game shop system, offering players the ability to purchase energy drinks with coins. The shop refreshes every 4 hours, generating 50 randomized offers based on available drinks and their rarity weights. Each offer includes an index (1-50), associated drink ID, assigned rarity, and batch timestamp.

The batch_ts field enables the application to determine when the current set of offers was generated, facilitating automatic refresh when the 4-hour window expires. Indexes on offer_index, drink_id, rarity, and batch_ts optimize query performance for retrieving and displaying shop contents. This model supports a dynamic economy where players can acquire rare items through purchases.

**Section sources**
- [database.py](file://database.py#L66-L74)

### SilkPlantation Model
The SilkPlantation model represents a player's silk plantation in the Silk City feature. Each plantation is associated with a player and has attributes including plantation name, number of silk trees, planting and harvest timestamps, status, investment cost, expected yield, investment level, and quality/weather modifiers.

The model tracks the lifecycle of a plantation from planting through harvest completion. The status field indicates the current state (growing, ready, harvesting, completed), while the harvest_ready_at field determines when the plantation is ready for harvest. The investment_level field (starter, standard, premium, master) determines the scale and potential yield of the plantation.

**Section sources**
- [database.py](file://database.py#L206-L227) - *Added in recent commit*
- [silk_city.py](file://silk_city.py#L40-L80) - *Added in recent commit*

### SilkInventory Model
The SilkInventory model tracks a player's silk inventory in the Silk City feature. Each inventory item is associated with a player and has attributes including silk type (raw, refined, premium), quantity, quality grade (100-500, where 300 is average), and production timestamp.

The model enables players to store different types of silk obtained from harvesting plantations. The quality_grade field affects the value when selling silk to NPC traders, creating an incentive for players to optimize their plantation quality. The relationship with Player allows for efficient retrieval of a player's complete silk inventory.

**Section sources**
- [database.py](file://database.py#L229-L243) - *Added in recent commit*
- [silk_city.py](file://silk_city.py#L210-L230) - *Added in recent commit*

### SilkTransaction Model
The SilkTransaction model records all silk-related transactions in the Silk City feature. Each transaction includes seller and buyer IDs, transaction type (buy, sell, trade, npc_sale), silk type, amount, price per unit, total price, and creation timestamp.

The model supports both player-to-player and player-to-NPC transactions, enabling a dynamic silk economy. The seller_id field can be null for NPC purchases, while buyer_id is always populated. The transaction_type field allows for filtering and analysis of different transaction types, supporting economic monitoring and analytics.

**Section sources**
- [database.py](file://database.py#L245-L267) - *Added in recent commit*
- [silk_city.py](file://silk_city.py#L280-L320) - *Added in recent commit*

## Business Rules and Game Mechanics

### Rarity-Based Inventory Sorting
The application implements a sophisticated sorting mechanism for player inventories based on rarity levels. The RARITY_ORDER constant in constants.py defines the hierarchy from most to least valuable: Special, Majestic, Absolute, Elite, Medium, Basic. When displaying a player's inventory, items are sorted first by rarity according to this order, then alphabetically by drink name.

This sorting behavior is implemented in the inventory display function, which uses the RARITY_ORDER.index() method to determine the sort position of each rarity level. The visual presentation groups items by rarity, with emoji indicators (from COLOR_EMOJIS) providing immediate visual feedback on item quality. This design encourages players to pursue higher rarity items and provides a clear progression path.

**Section sources**
- [database.py](file://database.py#L19-L38)
- [constants.py](file://constants.py#L25-L35)

### VIP Status and Collection Rate Modifications
VIP status significantly enhances gameplay by modifying collection rates and enabling special features. Players with active VIP status (vip_until > current timestamp) receive benefits including increased auto-search limits and potentially enhanced drop rates. The VIP system is managed through administrative commands that can grant VIP status to individual players or all players.

The auto_search_enabled field allows VIP players to perform automated searches, with the auto_search_count tracking daily usage and auto_search_reset_ts indicating when the count resets. The system also supports temporary boosts to the auto-search limit through the auto_search_boost_count and auto_search_boost_until fields, which can be granted by administrators for special events or rewards.

**Section sources**
- [database.py](file://database.py#L19-L38)
- [constants.py](file://constants.py#L45-L55)

### Silk Plantation Mechanics
The Silk City feature introduces a new gameplay mechanic centered around silk plantations. Players can create plantations at different investment levels (starter, standard, premium, master), each with different costs, tree counts, growth times, and yield ranges. The expected yield is calculated based on base yield, quality modifier (80-120%), and weather modifier (90-110%).

VIP players receive bonuses to silk production including a 20% increase in yield, 10% bonus to quality modifier, and 10% faster growth speed. The maximum number of active plantations per player is limited to 5. When a plantation is ready for harvest, players receive notifications and can collect their silk yield, which is distributed across different silk types (raw, refined, premium) based on probability weights.

**Section sources**
- [database.py](file://database.py#L206-L267) - *Added in recent commit*
- [silk_city.py](file://silk_city.py#L40-L150) - *Added in recent commit*
- [constants.py](file://constants.py#L100-L150) - *Updated in recent commit*

### Silk Market and Trading
The silk market implements a dynamic pricing system where prices fluctuate based on market conditions. The base prices for silk types are defined in constants.py, with raw silk at 30 coins, refined at 40 coins, and premium at 50 coins. Actual prices vary within ranges (raw: 25-35, refined: 35-45, premium: 45-55) to simulate market dynamics.

When selling silk to NPC traders, the final price is influenced by the silk's quality grade, with higher quality silk fetching better prices. The quality bonus is calculated as ±20% based on the difference from the average quality grade of 300. This creates an incentive for players to optimize their plantation quality to maximize profits.

**Section sources**
- [silk_city.py](file://silk_city.py#L280-L320) - *Added in recent commit*
- [constants.py](file://constants.py#L140-L170) - *Updated in recent commit*

### Shop Offer Generation and Pricing
The shop system follows a carefully balanced economic model. Shop offers are regenerated every 4 hours if the current batch is older than the refresh interval or if fewer than 50 offers exist. The generation process randomly selects drinks and assigns rarities based on weighted probabilities defined in the RARITIES constant, with Basic items being most common and Majestic items being rarest.

Pricing is determined by the SHOP_PRICES dictionary, which multiplies the base receiver prices by a SHOP_PRICE_MULTIPLIER (currently 3). This creates a balanced economy where players can sell items back at a lower price than purchase cost, preventing inflation and encouraging active gameplay. The pricing model ensures that rarer items have proportionally higher values, reinforcing their desirability.

**Section sources**
- [database.py](file://database.py#L347-L400)
- [constants.py](file://constants.py#L65-L75)

## Data Access Patterns and Sample Queries

### Retrieving User Inventory
The most common data access pattern involves retrieving a player's complete inventory with detailed information about each item. This requires joining the InventoryItem table with the EnergyDrink table to obtain drink names, descriptions, and images, while also considering the player's sorting preferences.

```sql
SELECT 
    ii.id,
    ii.quantity,
    ii.rarity,
    ed.name,
    ed.description,
    ed.image_path
FROM inventory_items ii
JOIN energy_drinks ed ON ii.drink_id = ed.id
WHERE ii.player_id = :user_id
ORDER BY 
    CASE ii.rarity 
        WHEN 'Special' THEN 0
        WHEN 'Majestic' THEN 1
        WHEN 'Absolute' THEN 2
        WHEN 'Elite' THEN 3
        WHEN 'Medium' THEN 4
        WHEN 'Basic' THEN 5
    END,
    ed.name ASC;
```

This query leverages the indexes on player_id and the relationship between inventory_items and energy_drinks to efficiently retrieve and sort the data. The application implements pagination with ITEMS_PER_PAGE items per page, reducing memory usage and improving response times for players with large inventories.

**Section sources**
- [database.py](file://database.py#L48-L62)
- [constants.py](file://constants.py#L35)

### Checking Cooldown Status
The application frequently needs to check whether a player can perform time-limited actions such as searching for energy drinks or claiming daily bonuses. This involves comparing the current timestamp with the last action timestamp stored in the Player model.

```sql
SELECT 
    user_id,
    coins,
    last_search,
    last_bonus_claim,
    vip_until,
    (strftime('%s', 'now') - last_search) as search_cooldown_remaining,
    (strftime('%s', 'now') - last_bonus_claim) as bonus_cooldown_remaining
FROM players 
WHERE user_id = :user_id;
```

The cooldown status is calculated by subtracting the last action timestamp from the current Unix timestamp. If the result is less than the cooldown period (SEARCH_COOLDOWN or DAILY_BONUS_COOLDOWN), the action is still on cooldown. VIP players may have reduced cooldowns or additional actions available through their boosted limits.

**Section sources**
- [database.py](file://database.py#L19-L38)
- [constants.py](file://constants.py#L15-L20)

### Admin Moderation Workflow
Administrators need to review pending additions, deletions, and edits to maintain game content quality. This requires querying the pending tables with status filters and joining with player and admin information for context.

```sql
SELECT 
    pa.id,
    pa.proposer_id,
    p.username as proposer_username,
    pa.name,
    pa.description,
    pa.is_special,
    pa.status,
    pa.created_at,
    a.username as reviewer_username,
    pa.reviewed_at,
    pa.review_reason
FROM pending_additions pa
LEFT JOIN players p ON pa.proposer_id = p.user_id
LEFT JOIN admin_users a ON pa.reviewed_by = a.user_id
WHERE pa.status = 'pending'
ORDER BY pa.created_at ASC;
```

This query retrieves all pending addition requests with associated proposer and reviewer information, allowing administrators to make informed decisions about content approval. Similar queries exist for pending deletions and edits, supporting a comprehensive moderation system.

**Section sources**
- [database.py](file://database.py#L87-L99)

### Retrieving Silk Plantation Data
To support the Silk City feature, the application needs to retrieve plantation data for players, including active plantations and their harvest status.

```sql
SELECT 
    sp.id,
    sp.plantation_name,
    sp.investment_level,
    sp.planted_at,
    sp.harvest_ready_at,
    sp.status,
    sp.expected_yield,
    sp.quality_modifier,
    sp.weather_modifier
FROM silk_plantations sp
WHERE sp.player_id = :user_id
ORDER BY 
    CASE sp.status
        WHEN 'ready' THEN 0
        WHEN 'growing' THEN 1
        WHEN 'completed' THEN 2
    END,
    sp.harvest_ready_at ASC;
```

This query retrieves all plantations for a player, sorting them by status priority (ready first) and then by harvest readiness time. This ensures that players see their most urgent plantations first in the interface.

**Section sources**
- [database.py](file://database.py#L206-L227) - *Added in recent commit*
- [silk_city.py](file://silk_city.py#L40-L80) - *Added in recent commit*

### Silk Inventory and Market Queries
The silk market functionality requires queries to retrieve player inventory and current market prices.

```sql
-- Get player's silk inventory
SELECT 
    si.silk_type,
    si.quantity,
    si.quality_grade,
    si.produced_at,
    st.base_price as base_price
FROM silk_inventory si
JOIN players p ON si.player_id = p.user_id
JOIN (
    SELECT 'raw' as type, 30 as base_price
    UNION SELECT 'refined', 40
    UNION SELECT 'premium', 50
) st ON si.silk_type = st.type
WHERE si.player_id = :user_id AND si.quantity > 0
ORDER BY si.silk_type;

-- Get current market prices
SELECT 
    silk_type,
    CASE 
        WHEN silk_type = 'raw' THEN CAST((25 + (RANDOM() % 11)) AS INTEGER)
        WHEN silk_type = 'refined' THEN CAST((35 + (RANDOM() % 11)) AS INTEGER)
        WHEN silk_type = 'premium' THEN CAST((45 + (RANDOM() % 11)) AS INTEGER)
    END as current_price
FROM (
    SELECT 'raw' as silk_type
    UNION SELECT 'refined'
    UNION SELECT 'premium'
);
```

These queries support the silk market interface, showing players their inventory with quality information and current market prices for trading decisions.

**Section sources**
- [database.py](file://database.py#L229-L267) - *Added in recent commit*
- [silk_city.py](file://silk_city.py#L210-L320) - *Added in recent commit*
- [constants.py](file://constants.py#L140-L170) - *Updated in recent commit*

## Data Validation and Constraints

### Field-Level Validation
The database schema implements comprehensive field-level validation through SQLAlchemy column constraints and application-level validation rules. Primary keys ensure entity uniqueness, with user_id serving as the primary key for Player and AdminUser tables, and auto-incrementing IDs for other entities.

String fields have appropriate length constraints inferred from their type definitions, while integer fields are validated to ensure non-negative values where appropriate (e.g., coins, quantities). Boolean fields are strictly typed to prevent invalid states. The application enforces additional validation rules in business logic, such as ensuring that rarity values belong to the predefined set of valid rarities.

Foreign key constraints maintain referential integrity between related entities, preventing orphaned records and ensuring that operations like cascading deletes work correctly. For example, when a player is deleted, all their inventory items are automatically removed due to the cascade="all, delete-orphan" setting on the relationship.

**Section sources**
- [database.py](file://database.py#L19-L100)

### Business Rule Validation
Beyond basic field validation, the application enforces complex business rules through application logic and database constraints. The shop offer generation process validates that only existing drinks are included in offers and that rarity assignments follow the weighted probability distribution defined in RARITIES.

Inventory operations validate that players cannot have negative quantities of items, with the decrement_inventory_item function automatically removing inventory records when quantity reaches zero. Purchase operations validate that players have sufficient coins before completing transactions, using database-level locking to prevent race conditions during concurrent purchases.

The moderation system validates that only authorized administrators can approve or reject requests, with level-based permissions ensuring that junior moderators cannot perform actions reserved for senior staff. All moderation actions are logged in the ModerationLog table, providing an audit trail for accountability.

For the Silk City feature, business rules validate that players cannot create more than the maximum number of plantations (5), that they have sufficient coins for investment, and that they cannot harvest plantations before they are ready. The quality grade for silk inventory is constrained to the range 100-500, with appropriate validation in the application logic.

**Section sources**
- [database.py](file://database.py#L2705-L2731)
- [silk_city.py](file://silk_city.py#L40-L150) - *Added in recent commit*

## Indexing and Performance Optimization

### Strategic Indexing
The database schema employs strategic indexing to optimize query performance for common access patterns. The Player table has an index on user_id (primary key) and additional indexes on vip_until and tg_premium_until to optimize queries for status checks.

The InventoryItem table features composite indexes on player_id, drink_id, and rarity, enabling efficient retrieval of player inventories, item counts, and rarity-based queries. The ShopOffer table has indexes on offer_index, drink_id, rarity, and batch_ts to support fast lookup and filtering of shop contents.

For the Silk City feature, new indexes have been added to optimize performance:
- idx_silk_plantation_player on player_id in silk_plantations table
- idx_silk_plantation_status on status in silk_plantations table
- idx_silk_plantation_harvest_time on harvest_ready_at in silk_plantations table
- idx_silk_inventory_player on player_id in silk_inventory table
- idx_silk_inventory_type on silk_type in silk_inventory table
- idx_silk_transaction_seller on seller_id in silk_transactions table
- idx_silk_transaction_buyer on buyer_id in silk_transactions table
- idx_silk_transaction_type on transaction_type in silk_transactions table
- idx_silk_transaction_date on created_at in silk_transactions table

These indexing strategies ensure that the application can handle growing data volumes without significant performance degradation.

**Section sources**
- [database.py](file://database.py#L48-L62)
- [database.py](file://database.py#L206-L267) - *Added in recent commit*

### Query Optimization Techniques
The application implements several query optimization techniques to minimize database load and improve response times. The get_or_refresh_shop_offers function uses a two-phase approach, first checking if a refresh is needed before querying the database, reducing unnecessary operations.

Relationship loading is optimized using SQLAlchemy's joinedload option when retrieving shop offers with drink details, eliminating the N+1 query problem. The application also implements caching at the application level for frequently accessed data like the list of energy drinks, reducing database queries for static content.

For inventory operations, the application uses database-level locking (with_for_update) during purchase and decrement operations to prevent race conditions while maintaining performance. Batch operations are used where appropriate, such as when granting VIP status to all players, to minimize the number of database round-trips.

For the Silk City feature, query optimization includes:
- Using joinedload to efficiently retrieve plantation data with player information
- Implementing batch operations for updating multiple plantations
- Using database-level locking during silk transactions to prevent race conditions
- Optimizing the harvest_ready_at index for efficient querying of ready plantations

**Section sources**
- [database.py](file://database.py#L347-L400)
- [silk_city.py](file://silk_city.py#L40-L150) - *Added in recent commit*

## Transaction Management

### Atomic Operations
The application ensures data consistency through careful transaction management, wrapping related operations in atomic transactions. When a player purchases a shop offer, the transaction includes deducting coins from the player's balance and adding the item to their inventory, ensuring that both operations succeed or fail together.

The purchase_shop_offer function uses a try-except block with explicit transaction rollback to handle errors, preventing partial updates that could lead to inconsistent states. Database-level locking (with_for_update) is used during balance checks and updates to prevent race conditions when multiple operations occur simultaneously.

Administrative operations like granting VIP status or auto-search boosts are also wrapped in transactions, with appropriate error handling to ensure that partial updates do not leave the database in an inconsistent state. The application uses SQLAlchemy's session management to automatically handle transaction boundaries in most cases, with manual control when complex operations require it.

For the Silk City feature, atomic transactions are used for:
- Creating new plantations (deducting coins and creating plantation record)
- Harvesting plantations (updating plantation status, adding silk to inventory, and awarding bonus coins)
- Selling silk to NPC traders (removing silk from inventory, adding coins to player balance, and recording transaction)

**Section sources**
- [database.py](file://database.py#L400-L450)
- [silk_city.py](file://silk_city.py#L40-L150) - *Added in recent commit*

### Error Handling and Rollback
Comprehensive error handling ensures that database transactions are properly managed even in exceptional circumstances. The application uses try-finally blocks to ensure that database sessions are properly closed, preventing connection leaks.

When exceptions occur during transaction processing, the application attempts to roll back the transaction to maintain data integrity. The purchase_shop_offer and add_auto_search_boost functions include explicit rollback attempts in their exception handlers, with careful consideration of potential secondary exceptions during the rollback process.

The application also logs transaction errors for monitoring and debugging purposes, helping administrators identify and resolve issues. This robust error handling ensures that the database remains consistent even under high load or unexpected conditions, maintaining a reliable user experience.

For the Silk City feature, error handling includes:
- Rolling back plantation creation if any part of the transaction fails
- Ensuring that harvest operations are atomic and consistent
- Properly handling exceptions during silk transactions
- Logging errors for debugging and monitoring

**Section sources**
- [database.py](file://database.py#L400-L450)
- [silk_city.py](file://silk_city.py#L40-L150) - *Added in recent commit*

## Data Lifecycle and Migration

### Data Retention Policies
The application implements data retention policies to manage storage requirements while preserving user progress. Player data is retained indefinitely unless explicitly deleted by the user, with inventory items cascading delete when their owner is removed.

Moderation logs and transaction records are retained for auditing purposes, with no automatic expiration. The BoostHistory table maintains a complete record of auto-search boost grants and expirations, supporting administrative review and player inquiries. Shop offer history is retained through the batch_ts system, allowing the application to track offer generations over time.

The application does not currently implement automated data purging, relying on the relatively small data footprint of individual records. Future enhancements could include archival policies for inactive accounts or periodic cleanup of expired temporary records.

For the Silk City feature, data retention includes:
- Permanent retention of silk transaction history for economic analysis
- Retention of completed plantation records for player statistics
- No automatic purging of silk inventory or plantation data

**Section sources**
- [database.py](file://database.py#L19-L100)

### Schema Migration Considerations
Future schema changes require careful planning to maintain data integrity and application functionality. The application currently uses a simple SQLite database with schema creation handled by SQLAlchemy's create_all method, which is suitable for initial deployment but not for production environments with existing data.

For future migrations, the application should implement a proper migration framework like Alembic to manage schema changes incrementally. This would allow for controlled updates to the database structure, including adding new fields, modifying constraints, or restructuring tables without data loss.

Migration strategies should include backup procedures, testing in staging environments, and rollback plans. When modifying existing fields, the application should maintain backward compatibility during transition periods. New features should be designed with extensibility in mind, using flexible data types and avoiding hard-coded assumptions that could complicate future changes.

For the Silk City feature, future migration considerations include:
- Potential addition of new silk types or quality tiers
- Expansion of plantation mechanics with new modifiers or features
- Integration with other game systems like community projects
- Performance optimizations for large-scale silk market operations

**Section sources**
- [database.py](file://database.py#L1-L50)

## Conclusion

The RELOAD application's database schema is a well-structured foundation for a feature-rich Telegram bot game. The entity-relationship model effectively captures the core gameplay mechanics while maintaining data integrity through appropriate constraints and relationships. The design balances normalization for data consistency with performance considerations through strategic indexing and query optimization.

Key strengths of the schema include its support for complex business rules like rarity-based sorting and VIP status effects, its robust moderation system for community-driven content, and its economic model with balanced shop pricing. The transaction management and error handling ensure data consistency even under concurrent operations.

The recent addition of the Silk City feature expands the game's mechanics with a new plantation and trading system. The new entities (SilkPlantation, SilkInventory, SilkTransaction) are well-integrated with the existing schema and follow the same design principles. The feature introduces new business rules for silk production and market dynamics, creating additional gameplay depth.

Future improvements could include implementing a formal migration framework, enhancing data retention policies, and expanding the analytics capabilities through additional logging. The current design provides a solid foundation that can accommodate these enhancements while continuing to support the game's evolving requirements.

The comprehensive documentation provided in this document enables developers and administrators to understand the data model, optimize queries, and implement new features with confidence in the underlying structure's integrity and performance characteristics.