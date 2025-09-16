# Collaborative Projects

<cite>
**Referenced Files in This Document**   
- [Bot_new.py](file://Bot_new.py)
- [database.py](file://database.py)
- [constants.py](file://constants.py)
</cite>

## Table of Contents
1. [Introduction](#introduction)
2. [Project Structure and Core Components](#project-structure-and-core-components)
3. [Project Creation and Initialization](#project-creation-and-initialization)
4. [User Participation Management](#user-participation-management)
5. [Collective Goal Tracking and Shared State](#collective-goal-tracking-and-shared-state)
6. [Event-Driven Progress Updates](#event-driven-progress-updates)
7. [Milestone-Based Reward Distribution](#milestone-based-reward-distribution)
8. [Synchronization and Data Consistency](#synchronization-and-data-consistency)
9. [Integration with VIP System](#integration-with-vip-system)
10. [Administrative Controls](#administrative-controls)
11. [Participation Inequality and Mitigation Strategies](#participation-inequality-and-mitigation-strategies)
12. [Performance Considerations for Large-Scale Collaborations](#performance-considerations-for-large-scale-collaborations)

## Introduction
The collaborative projects functionality in the EnergoBot system enables users to participate in community-driven initiatives where collective contributions advance shared objectives. Implemented primarily in `Bot_new.py` and supported by database models in `database.py`, this feature allows for the creation of cooperative goals, tracking of aggregate progress, and distribution of proportional rewards upon completion. The system integrates with user accounts, inventory, and currency (septims), while supporting administrative oversight and VIP-based enhancements. This document details the architecture, workflow, and technical implementation of the collaborative projects system.

## Project Structure and Core Components

```mermaid
erDiagram
COMMUNITY_PLANTATION {
int id PK
string title
string description
int created_at
bigint created_by
}
COMMUNITY_PROJECT_STATE {
int project_id PK FK
int goal_amount
int progress_amount
string status
int reward_total_coins
}
COMMUNITY_PARTICIPANT {
int id PK
int project_id FK
bigint user_id
int joined_at
int contributed_amount
boolean reward_claimed
}
COMMUNITY_CONTRIB_LOG {
int id PK
int project_id FK
bigint user_id
int amount
int ts
}
COMMUNITY_PLANTATION ||--o{ COMMUNITY_PROJECT_STATE : "has"
COMMUNITY_PLANTATION ||--o{ COMMUNITY_PARTICIPANT : "has"
COMMUNITY_PLANTATION ||--o{ COMMUNITY_CONTRIB_LOG : "has"
```

**Diagram sources**
- [database.py](file://database.py#L283-L309)

**Section sources**
- [Bot_new.py](file://Bot_new.py#L0-L5444)
- [database.py](file://database.py#L0-L3060)

## Project Creation and Initialization
Community projects are created through administrative commands or automated demo setup. The `create_community_plantation` function initializes a new project with a title, description, creator ID, and optional goal amount and total reward. Upon creation, the system automatically generates a corresponding `CommunityProjectState` record with default values (1000 septims goal, 250 septims total reward) if one does not already exist. Administrative users can create projects via the `/add_community_project` command or through the demo seed command, which populates sample projects for demonstration purposes.

**Section sources**
- [database.py](file://database.py#L689-L722)
- [Bot_new.py](file://Bot_new.py#L1409-L1441)

## User Participation Management
Users join collaborative projects through an explicit opt-in mechanism. The `join_community_project` function handles enrollment, ensuring the project exists, initializing its state if necessary, and creating a `CommunityParticipant` record if the user is not already registered. A locking mechanism prevents race conditions during concurrent join attempts. Once joined, users can view their contribution history and current standing within the project. The system maintains participation records with timestamps and contribution amounts, enabling transparent tracking of individual involvement.

**Section sources**
- [database.py](file://database.py#L769-L807)
- [Bot_new.py](file://Bot_new.py#L1830-L1847)

## Collective Goal Tracking and Shared State
Project progress is tracked through a shared state model centered on the `CommunityProjectState` entity. Each project maintains a `progress_amount` counter that accumulates contributions from all participants toward a defined `goal_amount`. The system uses database-level locking (`with_for_update`) during contribution processing to ensure atomic updates and prevent data corruption. Progress is displayed as a percentage bar in the project interface, providing real-time feedback on collective advancement. The state also tracks project status (active/completed), enabling conditional logic for contribution acceptance and reward distribution.

**Section sources**
- [database.py](file://database.py#L291-L297)
- [Bot_new.py](file://Bot_new.py#L1496-L1534)

## Event-Driven Progress Updates
Contributions to collaborative projects trigger immediate, event-driven updates to the shared state. When a user submits a contribution via the `contribute_to_community_project` function, the system validates the amount, checks project status, deducts septims from the user's balance, and atomically updates both the participant's contribution record and the project's total progress. If the contribution completes the project (progress ≥ goal), the status is automatically changed to "completed." A contribution log entry is recorded for audit purposes. The UI is refreshed to reflect the updated progress, creating a responsive feedback loop.

**Section sources**
- [database.py](file://database.py#L810-L874)
- [Bot_new.py](file://Bot_new.py#L1849-L1870)

## Milestone-Based Reward Distribution
Upon project completion, participants can claim proportional rewards based on their individual contributions. The `claim_community_reward` function calculates each user's share by dividing their contribution by the total project progress and multiplying by the `reward_total_coins`. For example, a user who contributed 100 septims to a project with 1000 total septims progress would receive 10% of the 250 septim reward pool (25 septims). The system prevents double claiming through the `reward_claimed` flag and validates that the project is completed and the user has a non-zero contribution before distribution.

**Section sources**
- [database.py](file://database.py#L895-L943)
- [Bot_new.py](file://Bot_new.py#L1872-L1899)

## Synchronization and Data Consistency
The collaborative projects system employs multiple synchronization mechanisms to maintain data consistency. Database row-level locks (`with_for_update`) ensure atomic updates to project state and participant records during contributions. Application-level asyncio locks prevent a single user from making concurrent contributions or joining the same project multiple times. All database operations are wrapped in transactions with proper commit/rollback handling to maintain integrity. The system also includes defensive checks, such as verifying project existence and participant status, before processing any actions.

**Section sources**
- [Bot_new.py](file://Bot_new.py#L1830-L1847)
- [database.py](file://database.py#L810-L874)

## Integration with VIP System
The collaborative projects functionality integrates with the VIP system to provide enhanced contribution rates or other benefits, though specific VIP contribution multipliers are not explicitly implemented in the current codebase. VIP status is determined by the `is_vip` function, which checks the `vip_until` timestamp against the current time. While the existing code does not modify contribution amounts based on VIP status, the architecture supports such enhancements through the centralized contribution processing function, where VIP-based multipliers could be applied to user inputs before updating the shared state.

**Section sources**
- [database.py](file://database.py#L2509-L2515)
- [admin2.py](file://admin2.py#L374-L456)

## Administrative Controls
Administrators have extensive controls over collaborative projects. They can create new projects, seed demonstration projects, and manage user accounts including VIP status allocation through commands like `/addvip`. The system distinguishes between administrative levels, with project creation and VIP management restricted to higher-level administrators (level 3 and Creator). Admins can view project statistics, monitor contributions, and potentially intervene in project states if needed. The moderation system logs administrative actions for audit purposes, ensuring accountability in project management.

**Section sources**
- [admin2.py](file://admin2.py#L374-L456)
- [Bot_new.py](file://Bot_new.py#L1409-L1441)

## Participation Inequality and Mitigation Strategies
The current implementation may experience uneven participation, as users can contribute arbitrary amounts (10, 50, 100, 500 septims) with no minimum requirement. This could lead to scenarios where a few users dominate project completion. Potential mitigation strategies include implementing contribution scaling, where smaller contributions receive proportionally higher recognition, or introducing tiered reward structures that incentivize broader participation. The system could also incorporate progress-based milestones that distribute partial rewards, encouraging sustained engagement rather than last-minute large contributions.

**Section sources**
- [Bot_new.py](file://Bot_new.py#L1536-L1552)

## Performance Considerations for Large-Scale Collaborations
The collaborative projects system is designed to handle large-scale collaborations efficiently. Database indexing on key fields (`project_id`, `user_id`, `progress_amount`) ensures fast queries even with hundreds of participants. The use of batch operations and connection pooling minimizes database overhead. However, performance could be optimized further by implementing caching for frequently accessed project statistics and using asynchronous processing for non-critical operations like contribution logging. The current locking strategy may create bottlenecks under extreme concurrency, suggesting potential improvements through optimistic concurrency control or sharding for very large projects.

**Section sources**
- [database.py](file://database.py#L877-L892)
- [Bot_new.py](file://Bot_new.py#L1496-L1534)