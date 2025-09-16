# Subscription Management

<cite>
**Referenced Files in This Document**   
- [Bot_new.py](file://Bot_new.py)
- [constants.py](file://constants.py)
- [database.py](file://database.py)
- [admin2.py](file://admin2.py)
</cite>

## Table of Contents
1. [VIP Purchase Process](#vip-purchase-process)
2. [VIP Menu Interface](#vip-menu-interface)
3. [Database Interactions](#database-interactions)
4. [Error Handling and Transaction Failures](#error-handling-and-transaction-failures)
5. [Administrative VIP Management](#administrative-vip-management)
6. [System Consistency Considerations](#system-consistency-considerations)

## VIP Purchase Process

The VIP subscription system enables users to purchase VIP status through the `buy_vip` function in Bot_new.py, which handles the complete transaction workflow. The process begins when a user selects a VIP duration option from the VIP menu interface. The system integrates with constants.py to retrieve the VIP cost and duration values through the `VIP_COSTS` and `VIP_DURATIONS_SEC` dictionaries, which define the pricing structure and time periods for different VIP tiers.

When a user initiates a VIP purchase, the system first validates that the requested plan exists in both `VIP_COSTS` and `VIP_DURATIONS_SEC`. It then checks if the user has sufficient currency to complete the transaction by calling the `purchase_vip` function in database.py. This function performs a database transaction that verifies the user's coin balance against the required cost before proceeding. If the user has sufficient funds, the system deducts the appropriate amount of coins and extends the user's VIP status by the selected duration. The transaction is atomic, ensuring that either both the coin deduction and VIP extension occur, or neither does, maintaining data consistency.

The purchase process includes protection against double-clicks through an asyncio lock mechanism that prevents concurrent purchase attempts by the same user. After a successful transaction, the system updates the user's VIP expiration timestamp and provides feedback with the new expiration date and remaining coin balance. The integration between Bot_new.py and database.py ensures a seamless user experience while maintaining data integrity throughout the purchase workflow.

**Section sources**
- [Bot_new.py](file://Bot_new.py#L2518-L2571)
- [constants.py](file://constants.py#L40-L44)
- [database.py](file://database.py#L2517-L2556)

## VIP Menu Interface

The VIP menu interface in Bot_new.py presents users with clear duration options for purchasing VIP status, creating an intuitive user experience. When users access the VIP menu through the `show_vip_menu` function, they are presented with three duration options: 1 Day, 7 Days, and 30 Days, each with corresponding pricing information. The interface displays comprehensive details about VIP benefits, including special privileges like a leaderboard badge, reduced cooldown times for searches and daily bonuses, doubled coin rewards from searches, and enhanced search reminder functionality.

The menu dynamically displays the user's current VIP status, showing when their VIP membership expires if active. It also provides information about the VIP auto-search feature, indicating whether it's enabled or disabled and showing the user's current daily usage against their limit. For users with active auto-search boosts, the interface displays additional details about their boosted search capacity, remaining time on the boost, and the expiration date of the boost.

The interface is fully localized, supporting multiple languages through the text translation system. Each VIP duration option is presented as an interactive button that triggers the `buy_vip` function with the corresponding plan key ('1d', '7d', or '30d'). The menu also includes navigation options to return to the previous menu or go back to the main menu, ensuring users can easily navigate the application. The design prioritizes clarity and user experience, presenting all necessary information while minimizing cognitive load.

**Section sources**
- [Bot_new.py](file://Bot_new.py#L2791-L2865)

## Database Interactions

The VIP subscription system relies on robust database interactions in database.py to store and retrieve VIP expiration timestamps through the Player model. The Player class contains a `vip_until` column that stores the Unix timestamp indicating when a user's VIP status expires. This design allows for efficient queries to determine VIP status and supports the extension of existing VIP periods by adding duration to the current expiration time.

The system implements several key functions for managing VIP data. The `get_vip_until` function retrieves the expiration timestamp for a given user ID, returning 0 if no VIP status exists. The `is_vip` function builds upon this by comparing the stored expiration timestamp with the current time to determine if VIP status is currently active. This two-step approach separates data retrieval from business logic, promoting code reusability and maintainability.

When processing VIP purchases, the `purchase_vip` function uses a database transaction with row-level locking to prevent race conditions during concurrent access. The function first checks the user's coin balance, then calculates the new VIP expiration time by adding the purchased duration to either the current expiration time (if it's in the future) or the current time (if the VIP has expired or never existed). This ensures that VIP periods are properly extended rather than overwritten, allowing users to stack multiple purchases.

The database schema is designed with data integrity in mind, using appropriate data types and constraints. The `vip_until` column is defined as an Integer with a default value of 0, ensuring that all players have a defined VIP expiration time. The use of Unix timestamps provides timezone-agnostic storage and simplifies duration calculations, while the integration with SQLAlchemy ORM ensures type safety and query optimization.

**Section sources**
- [database.py](file://database.py#L2500-L2507)
- [database.py](file://database.py#L2517-L2556)

## Error Handling and Transaction Failures

The VIP subscription system implements comprehensive error handling patterns to manage transaction failures, particularly those resulting from insufficient funds. When a user attempts to purchase VIP status without sufficient currency, the `purchase_vip` function in database.py detects this condition and returns a structured response with the reason "not_enough_coins". This response is then handled by the `buy_vip` function in Bot_new.py, which displays an appropriate localized error message to the user through the Telegram interface.

The system employs multiple layers of protection to ensure transactional integrity and prevent race conditions. An asyncio lock mechanism prevents double-clicks by serializing purchase attempts from the same user, while database-level row locking ensures that concurrent requests from different sources don't interfere with each other. These protections work together to prevent scenarios where a user might accidentally make multiple purchases or where race conditions could lead to inconsistent account states.

In addition to insufficient funds, the system handles various other potential error conditions. Network issues, database connectivity problems, and unexpected exceptions are caught and handled gracefully, with appropriate rollback of any partial transactions to maintain data consistency. The error handling code includes try-except blocks with proper resource cleanup in finally clauses, ensuring that database connections are properly closed even when exceptions occur.

The user interface provides clear feedback for different error scenarios, using distinct messages for insufficient funds versus other technical issues. This differentiation helps users understand whether they need to acquire more currency or whether the issue is temporary and might resolve with a retry. The error messages are localized to support multiple languages, maintaining a consistent user experience across different locales.

**Section sources**
- [Bot_new.py](file://Bot_new.py#L2518-L2571)
- [database.py](file://database.py#L2517-L2556)

## Administrative VIP Management

Administrative commands in admin2.py provide privileged users with the ability to manually assign VIP status through the `addvip_command` function, offering powerful management capabilities for system administrators. This command allows administrators with appropriate privileges (Creator or level 3 admins) to grant VIP status to individual users or to all users simultaneously. The command accepts a username (or "all" for bulk assignment) and the number of days for the VIP duration, converting this to seconds for consistent storage in the database.

When assigning VIP status to a specific user, the system first validates the target user's existence in the database by username. It then calculates the new VIP expiration time by adding the specified duration to either the current expiration time (if the VIP is still active) or the current time (if the VIP has expired). This approach ensures that VIP periods are properly extended rather than overwritten, maintaining consistency with the user purchase system.

For bulk assignments to all users, the system iterates through all player records in a single database transaction, updating each user's VIP expiration time. This operation is performed with proper error handling and transaction rollback capabilities to prevent partial updates in case of failures. The command provides feedback on the number of users affected, allowing administrators to verify the operation's scope.

The administrative VIP assignment system maintains consistency with the regular purchase system by using the same underlying database structure and timestamp calculations. This ensures that VIP status granted through administrative commands functions identically to VIP status purchased by users, with the same benefits and expiration behavior. The system also logs administrative actions for audit purposes, maintaining a record of who granted VIP status and when, which supports accountability and troubleshooting.

**Section sources**
- [admin2.py](file://admin2.py#L374-L456)

## System Consistency Considerations

The VIP subscription system maintains consistency across multiple components through careful design and implementation patterns. The integration between Bot_new.py, constants.py, database.py, and admin2.py ensures that VIP duration calculations, cost structures, and expiration logic are consistent regardless of whether VIP status is acquired through purchase or administrative assignment. All components use the same `VIP_DURATIONS_SEC` dictionary from constants.py for duration calculations, eliminating discrepancies that could arise from hardcoded values.

The system employs a unified approach to VIP expiration management, using Unix timestamps stored in the `vip_until` column of the Player model. This centralized storage ensures that all components read from and write to the same data source, preventing inconsistencies that could occur with distributed state management. The `is_vip` function provides a single source of truth for VIP status determination, which is used throughout the application to enable or disable VIP-specific features.

To maintain consistency during concurrent operations, the system implements both application-level and database-level locking mechanisms. The asyncio locks in Bot_new.py prevent race conditions at the application level, while the database transactions with row locking in database.py ensure data integrity at the persistence level. These complementary mechanisms work together to prevent scenarios where multiple operations could interfere with each other, such as a user attempting to purchase VIP while an administrator is granting it.

The error handling and transaction management systems are designed to maintain consistency even in failure scenarios. Database transactions are atomic, ensuring that partial updates don't leave the system in an inconsistent state. When errors occur, the system rolls back changes and provides clear feedback, allowing users and administrators to understand the system state and take appropriate action. This comprehensive approach to consistency ensures reliable operation of the VIP subscription system under various conditions.

**Section sources**
- [Bot_new.py](file://Bot_new.py#L2518-L2571)
- [constants.py](file://constants.py#L40-L44)
- [database.py](file://database.py#L2500-L2556)
- [admin2.py](file://admin2.py#L374-L456)