# Administrative System

<cite>
**Referenced Files in This Document**   
- [admin.py](file://admin.py)
- [admin2.py](file://admin2.py)
- [database.py](file://database.py)
- [constants.py](file://constants.py)
</cite>

## Table of Contents
1. [Multi-Level Permission Structure](#multi-level-permission-structure)
2. [Content Moderation Workflows](#content-moderation-workflows)
3. [User Management Commands](#user-management-commands)
4. [System Configuration Capabilities](#system-configuration-capabilities)
5. [Command Registration and Execution](#command-registration-and-execution)
6. [Database Schema Relationships](#database-schema-relationships)
7. [Security Considerations](#security-considerations)
8. [Common Issues and Mitigation Strategies](#common-issues-and-mitigation-strategies)

## Multi-Level Permission Structure

The administrative command system implements a hierarchical role-based access control (RBAC) model across two primary modules: `admin.py` for basic administrative functions and `admin2.py` for elevated privileges. The permission structure is defined by three distinct administrative levels (1-3), with additional special status for bootstrap creators defined in `constants.py`.

Administrators are stored in the `admin_users` table within the database, where each record contains a `user_id`, optional `username`, and `level` field. The system recognizes two types of privileged users: bootstrap creators (defined by `ADMIN_USERNAMES` in `constants.py`) and level-based administrators. Bootstrap creators inherit the highest level of authority regardless of their database-stored level, effectively granting them permanent level 3 equivalent privileges.

The permission hierarchy is strictly enforced through conditional checks at the beginning of each administrative command. In `admin.py`, the `admin_command` function performs the initial authorization check, verifying whether the executing user is either a registered administrator (via `db.is_admin(user.id)`) or a bootstrap creator (via `user.username in ADMIN_USERNAMES`). Users failing this check receive an immediate "No permissions" response.

Higher-level commands in `admin2.py` implement more granular access control through the `_is_creator_or_lvl3` helper function, which explicitly checks for either bootstrap creator status or level 3 authorization. This function is used as a gatekeeper for the most sensitive operations, including financial transactions, system configuration changes, and audit log access.

The system implements dynamic command visibility based on the administrator's level. When a user invokes the `/admin` command without arguments, the help text is generated dynamically according to their permission level. Level 3 administrators and bootstrap creators receive additional command options for managing other administrators, while lower-level administrators see only the commands they are authorized to execute.

**Section sources**
- [admin.py](file://admin.py#L0-L15)
- [admin2.py](file://admin2.py#L112-L128)
- [constants.py](file://constants.py#L70-L72)

## Content Moderation Workflows

The administrative system implements a comprehensive content moderation workflow centered around the `PendingAddition` model and related entities for managing user-generated content. This workflow enables a structured process for proposing, reviewing, and approving changes to the energy drink catalog, ensuring quality control and preventing unauthorized modifications.

The moderation system supports three primary content modification requests: additions (`/add`), deletions (`/delrequest`), and edits (`/editdrink`). Each request type follows a consistent lifecycle managed through dedicated database tables: `pending_additions`, `pending_deletions`, and `pending_edits`. These tables store essential metadata including the proposer's ID, request details, status (pending/approved/rejected), timestamps, and reviewer information.

The workflow begins when a user submits a request through the appropriate command. For example, the `/add` command initiates a new `PendingAddition` record with status "pending". Administrators can view all pending requests through the `/requests` command, which presents a list with interactive buttons for approval and rejection. The system implements a sophisticated permission model for moderation actions: level 1+ administrators can approve additions, level 2+ or creators can approve deletions, and level 3 or creators must approve edits.

The approval process is implemented in `Bot_new.py` through callback handlers like `approve_pending`, which first verifies the administrator's credentials before processing the request. The system prevents conflict of interest by prohibiting users from approving their own requests. Upon approval, the system executes the requested database operation (e.g., adding a new energy drink) and updates the request status to "approved". The proposer receives a notification of the decision, and other administrators are informed through broadcast messages to maintain transparency.

Rejection of requests follows a similar pattern but includes an additional step for providing rejection reasons. The system uses `ForceReply` functionality to prompt the administrator for a justification, which is then stored in the `review_reason` field and communicated to the proposer. This feedback mechanism helps users understand why their submissions were not accepted and improves the quality of future requests.

**Section sources**
- [database.py](file://database.py#L87-L99)
- [Bot_new.py](file://Bot_new.py#L2785-L2801)
- [Bot_new.py](file://Bot_new.py#L2846-L2867)

## User Management Commands

The administrative system provides a comprehensive suite of user management commands that enable administrators to control access, assign roles, and maintain the administrative hierarchy. These commands are primarily implemented in `admin.py` and focus on the creation, modification, and removal of administrative accounts through the `/admin` command interface.

The user management system supports three administrative levels with distinct roles: level 1 (Junior Moderator), level 2 (Senior Moderator), and level 3 (Head Administrator). These roles are visually represented in the `/admin list` output, which displays administrators sorted by role priority (Creators first, then by level descending). The system automatically synchronizes administrator usernames by querying Telegram's API when displaying the list, ensuring that username changes are reflected in the database through the `add_admin_user` function.

The `/admin add` command allows authorized administrators (level 3 or creators) to add new administrators by specifying a user ID, optional username, and level (defaulting to 1). The command supports multiple input methods: direct user ID specification or reply-to-message functionality, which extracts the user ID from the replied message. When adding an administrator, the system first attempts to retrieve the current username from Telegram's API if not provided, ensuring accurate user identification.

Administrative level modifications are handled through the `/admin level` command, which requires the target user ID and new level as parameters. This command implements strict validation to ensure the level is within the valid range (1-3) and properly handles both reply-based and direct ID specification methods. Upon successful level change, the system logs the action in the `moderation_logs` table with details of the change for audit purposes.

Administrator removal is implemented through the `/admin remove` command, which permanently deletes an administrator record from the `admin_users` table. The system provides appropriate feedback to indicate whether the removal was successful or if the specified user was not found in the administrator database. All user management operations are logged through the `insert_moderation_log` function, creating an immutable audit trail of administrative changes.

**Section sources**
- [admin.py](file://admin.py#L159-L183)
- [admin.py](file://admin.py#L103-L133)
- [admin.py](file://admin.py#L76-L101)

## System Configuration Capabilities

The administrative system provides extensive system configuration capabilities through the `admin2.py` module, enabling privileged administrators to manage inventory levels, financial transactions, and system parameters. These capabilities are restricted to level 3 administrators and bootstrap creators, ensuring that critical system settings can only be modified by the most trusted personnel.

The inventory management system centers around the `BonusStock` and `TgPremiumStock` database models, which track available quantities of various bonuses and Telegram Premium subscriptions. Administrators can query current stock levels using the `/stock` and `/tgstock` commands, which retrieve values from their respective database tables. The system supports both incremental adjustments (`/stockadd`, `/tgadd`) and absolute value setting (`/stockset`, `/tgset`), providing flexibility in inventory management.

Financial operations are implemented through commands like `/addcoins`, which allows bootstrap creators to directly credit user accounts with coins. This command supports both direct user ID specification and reply-to-message functionality, making it convenient to reward users who have interacted with the bot. The system also manages purchase receipts through the `PurchaseReceipt` model, allowing administrators to verify transactions and update their status through commands like `/verifyreceipt`.

The system includes specialized commands for managing user privileges and bonuses. The `/addvip` command grants VIP status to individual users or all users simultaneously, updating the `vip_until` field in the `players` table. Similarly, the `/addautosearch` command modifies the auto-search capabilities of users by adjusting the `auto_search_boost_count` and `auto_search_boost_until` fields, effectively granting temporary increases in daily search limits.

Administrative oversight is enhanced through comprehensive reporting commands. The `/listboosts` command displays all users with active auto-search boosts, while `/booststats` provides statistical insights into boost usage patterns. The `/boosthistory` command offers detailed audit trails of boost grants and removals, including information about which administrator performed each action. These reporting capabilities enable administrators to monitor system usage and identify potential abuse patterns.

**Section sources**
- [admin2.py](file://admin2.py#L235-L252)
- [database.py](file://database.py#L1698-L1740)
- [admin2.py](file://admin2.py#L112-L128)

## Command Registration and Execution

The administrative command system follows a structured pattern for command registration and execution, with commands being registered in the main bot application and implemented as asynchronous handler functions in the `admin.py` and `admin2.py` modules. Each command follows a consistent execution flow that includes permission verification, argument parsing, business logic execution, and response generation.

Commands are registered with the Telegram bot framework using the `CommandHandler` class, associating command strings (e.g., "/admin", "/admin2") with their corresponding handler functions (`admin_command`, `admin2_command`). When a user invokes a command, the Telegram API delivers an `Update` object containing the message details, which is passed to the handler function along with a `ContextTypes.DEFAULT_TYPE` object providing access to the bot instance and other contextual information.

The execution flow begins with permission verification, where the handler function immediately checks whether the invoking user has sufficient privileges to execute the command. This is implemented through direct database queries (`db.is_admin`, `db.get_admin_level`) and comparisons with bootstrap creator usernames from `constants.py`. Users lacking appropriate permissions receive an immediate error response and the function returns without further processing.

For commands with arguments, the handler parses the `context.args` array to extract command parameters. The system supports multiple argument parsing patterns, including positional arguments, reply-to-message context, and mixed input methods. For example, the `/admin add` command can accept a user ID as a direct argument or extract it from a replied message, providing flexibility in command usage.

After successful permission and argument validation, the handler executes the core business logic by calling appropriate repository methods from the `database.py` module. These methods perform the actual database operations, such as adding or removing administrators, modifying inventory levels, or updating user records. Upon completion, the handler generates a human-readable response message indicating the result of the operation, which is sent back to the user through the `update.message.reply_text` method.

All administrative actions that modify system state are accompanied by audit logging through the `insert_moderation_log` function, which records the actor ID, action type, target ID, and relevant details in the `moderation_logs` table. This creates a comprehensive audit trail that can be used for security monitoring and incident investigation.

**Section sources**
- [admin.py](file://admin.py#L0-L15)
- [admin2.py](file://admin2.py#L112-L128)
- [admin.py](file://admin.py#L159-L183)

## Database Schema Relationships

The administrative system's functionality is underpinned by a well-defined database schema that establishes clear relationships between administrative entities, user data, and moderation workflows. The schema is implemented using SQLAlchemy ORM and consists of several interconnected tables that support the system's role-based access control and content moderation features.

The core administrative entity is the `AdminUser` class, which represents administrators in the system. This table has a primary key on `user_id` and includes fields for `username` and `level`. The `level` field implements the three-tier permission hierarchy, with values 1-3 corresponding to Junior Moderator, Senior Moderator, and Head Administrator roles respectively. This table serves as the foundation for all permission checks throughout the system.

The content moderation system is built around several related tables: `PendingAddition`, `PendingDeletion`, and `PendingEdit`. These tables share a common structure with fields for `proposer_id` (linking to the user who submitted the request), `status`, `created_at`, `reviewed_by`, and `reviewed_at`. The `PendingAddition` table includes fields for `name` and `description` of the proposed energy drink, while `PendingDeletion` references existing drinks through `drink_id`, and `PendingEdit` specifies both the `field` to be modified and the `new_value`.

Administrative actions are audited through the `ModerationLog` table, which records all significant administrative operations. This table includes fields for `actor_id` (the administrator performing the action), `action` (a string identifier for the type of action), `request_id` (for moderation actions), `target_id` (for user-targeted actions), and `details` (additional context). This comprehensive logging enables full traceability of administrative decisions and system changes.

The system also includes specialized tables for managing inventory and user privileges. The `BonusStock` table tracks available quantities of various bonuses by `kind`, while `TgPremiumStock` maintains the count of available Telegram Premium subscriptions. User privilege management is supported by fields in the `Player` table, including `vip_until`, `auto_search_boost_count`, and `auto_search_boost_until`, which control access to premium features.

These database entities are interconnected through foreign key relationships and application-level logic, creating a cohesive system where administrative commands translate directly into database operations. The schema design emphasizes data integrity through appropriate indexing, constraints, and transactional safety, ensuring reliable operation even under concurrent access.

**Section sources**
- [database.py](file://database.py#L120-L160)
- [database.py](file://database.py#L87-L99)
- [database.py](file://database.py#L160-L180)

## Security Considerations

The administrative system incorporates several security measures to protect against unauthorized access, privilege escalation, and data integrity violations. These considerations are implemented through a combination of role-based access control, input validation, audit logging, and secure coding practices that collectively create a robust security posture for privileged operations.

The primary security mechanism is the multi-level permission system, which strictly enforces the principle of least privilege. Each administrative command begins with a permission check that verifies the user's authorization level before proceeding with any sensitive operations. The system distinguishes between bootstrap creators (defined in `constants.py`) and level-based administrators, with creators having immutable privileges that cannot be revoked through administrative commands. This design prevents scenarios where all administrative privileges could be accidentally or maliciously removed.

To prevent privilege escalation vulnerabilities, the system implements strict validation of administrative level changes. Only level 3 administrators and bootstrap creators can modify administrator levels, add new administrators, or remove existing ones. The `/admin level` command includes validation to ensure that the target level is within the valid range (1-3), preventing attempts to create higher-than-allowed privilege levels. Additionally, the system prevents administrators from modifying their own privileges, eliminating a potential attack vector.

Input validation is implemented throughout the administrative command handlers to prevent injection attacks and data corruption. Command arguments are parsed and validated before being used in database operations, with appropriate type conversion and range checking. For example, the `/stockadd` and `/stockset` commands validate that numeric arguments are integers and that stock levels are not set to negative values. The system also validates user IDs and ensures they correspond to existing users before performing operations that affect user accounts.

Comprehensive audit logging provides an additional layer of security by creating an immutable record of all administrative actions. The `insert_moderation_log` function captures critical information about each privileged operation, including the actor, action type, target, and details. This audit trail enables post-incident analysis and helps detect suspicious activity. The system also notifies other administrators of significant moderation decisions, creating a peer-review mechanism that increases transparency and accountability.

The database schema includes several security-oriented design elements. The `admin_users` table was migrated to include the `level` column with a default value of 1, ensuring that legacy administrators are assigned appropriate privilege levels. The system uses database transactions with appropriate isolation levels when modifying critical data, preventing race conditions and ensuring data consistency during concurrent access.

**Section sources**
- [admin.py](file://admin.py#L76-L101)
- [admin2.py](file://admin2.py#L112-L128)
- [database.py](file://database.py#L2302-L2311)

## Common Issues and Mitigation Strategies

The administrative system may encounter several common issues related to permission management, data consistency, and user experience. These issues have been anticipated in the system design, and appropriate mitigation strategies have been implemented to ensure reliable operation and maintain security.

One potential issue is username drift, where an administrator changes their Telegram username, potentially breaking the link between their account and administrative privileges. The system mitigates this through proactive username synchronization in the `/admin list` command, which queries Telegram's API to retrieve the current username and updates the database if necessary. This ensures that the system always has accurate username information for all administrators, preventing access issues due to username changes.

Another common issue is the potential for race conditions when multiple administrators attempt to process the same moderation request simultaneously. The system addresses this through the use of database transactions with appropriate locking mechanisms in the repository methods. When an administrator approves or rejects a request, the database operation is performed within a transaction that ensures atomicity, preventing conflicting decisions from being applied to the same request.

Permission escalation vulnerabilities are mitigated through strict access control and validation. The system prevents administrators from granting themselves higher privileges by requiring level 3 or creator status for all administrative modifications. Additionally, the system implements a separation of duties for different types of moderation actions, ensuring that no single administrator has unchecked power over all content modification types.

Data inconsistency issues are prevented through comprehensive error handling and transaction management. Repository methods use try-catch blocks to handle database exceptions and implement proper rollback procedures when errors occur. For example, when purchasing a shop offer, the system uses a transaction to ensure that both the coin deduction and inventory update are completed successfully, or both are rolled back in case of failure.

The system also addresses potential notification failures by implementing best-effort delivery with error suppression. When sending notifications to users or other administrators about moderation decisions, the system uses `asyncio.gather` with `return_exceptions=True` to ensure that a failure in one notification does not prevent others from being delivered. This maintains system responsiveness even when individual message deliveries fail.

Finally, the system includes safeguards against command misuse through comprehensive input validation and usage guidance. Help texts provide clear examples of correct command syntax, and handlers validate all arguments before processing. For commands with destructive potential, such as `/admin remove`, the system provides clear feedback about the outcome, indicating whether the operation was successful or if the target was not found, preventing confusion about the system state.

**Section sources**
- [admin.py](file://admin.py#L49-L78)
- [Bot_new.py](file://Bot_new.py#L2831-L2844)
- [admin2.py](file://admin2.py#L159-L183)