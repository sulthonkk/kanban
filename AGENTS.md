# Momentum Project

## Business Requirements

- An MVP of a Kanban style Project Management application as a web app  
- The web app should only have 1 board
- The board has fixed 5 columns that can be renamed  
- Each card has a title and details only
- Drag and drop interface to move cards between columns
- Add a new card to a column; delete an existing card
- No more functionality: no archive, no search/filter. Keep it simple.
- The priority is a slick, professional, gorgeous UI/UX with very simple features
- The app should open with dummy data populated for the single board

## Technical Details

- Implemented as a modern NextJS app, client rendered
- The NextJS app should be created in a subdirectory `frontend`
- No persistence
- No user management for the MVP
- Use popular libraries
- As simple as possible but with an elegant UI

## Color Scheme

- Accent Yellow: `#ecad0a` - accent lines, highlights
- Blue Primary: `#209dd7` - links, key sections
- Purple Secondary: `#753991` - submit buttons, important actions
- Dark Navy: `#032147` - main headings
- Gray Text: `#888888` - supporting text, labels

## Strategy

1. Write plan with success criteria for each phase to be checked off. Include project scaffolding, including .gitignore, and rigorous unit testing.
2. Execute the plan ensuring all critiera are met
3. Carry out extensive integration testing with Playwright or similar, fixing defects
4. Only complete when the MVP is finished and tested, with the server running and ready for the user

## Coding standards

1. Use latest versions of libraries and idiomatic approaches as of today
2. Keep it simple - NEVER over-engineer, ALWAYS simplify, NO unnecessary defensive programming. No extra features - focus on simplicity.
3. Be concise. Keep README minimal. IMPORTANT: no emojis ever


## Starting Point

A working frontend MVP already exists.

This project is **NOT** a greenfield project.

The existing frontend has already been implemented using Next.js and customized beyond the original course implementation.

The frontend currently includes:

- Modern responsive UI
- Customized design and styling
- Single Kanban board
- Five renameable columns
- Drag and drop functionality
- Card creation
- Card editing
- Card deletion
- Local state management
- Dummy data

The goal of this project is to evolve the existing frontend into a complete full-stack application.

Do NOT recreate the frontend.

Do NOT generate another Next.js project.

Always build on top of the existing codebase.

Before making any implementation changes:

1. Review the existing frontend.
2. Understand how the current application works.
3. Reuse existing components whenever possible.
4. Preserve the current UI and UX.
5. Extend instead of replacing.

The existing frontend should remain the foundation of the project.

---

## Documentation

All project documentation lives inside the `docs/` directory.

Before starting any implementation, read:

docs/PLAN.md

`PLAN.md` is the primary source of truth for this project.

Follow its architecture, implementation phases, milestones and success criteria throughout development.

Whenever implementation changes significantly, update the relevant documentation inside the `docs/` directory to keep it synchronized with the codebase.

---

## Business Requirements

The application should support:

- User sign in
- One Kanban board per signed-in user
- Five fixed columns that can be renamed
- Cards containing:
  - title
  - details
- Drag and drop cards
- Create cards
- Edit cards
- Delete cards

An AI assistant should be available in a sidebar and capable of:

- creating cards
- editing cards
- moving cards
- deleting cards

Keep the application intentionally simple.

Do NOT implement extra features such as:

- archive
- labels
- comments
- notifications
- search
- filters
- teams

unless explicitly requested.

---

## Backend

Create a FastAPI backend inside:

backend/

Responsibilities include:

- Authentication
- Board management
- Card CRUD
- AI endpoints
- Database access

Expose clean REST APIs for the frontend.

---

## Database

Use SQLite.

Automatically create the database if it does not exist.

Although the MVP only supports one board per user, design the schema with future multi-user support in mind.

---

## Authentication

For the MVP, authentication may use hardcoded credentials:

Username:
user

Password:
password

Keep the implementation simple while allowing future expansion.

---

## AI Integration

Use OpenRouter for all AI requests.

Store the API key in:

.env

using:

OPENROUTER_API_KEY=...

Store the model in:

OPENROUTER_MODEL=...

For development, use:

openai/gpt-oss-20b:free

Do not hardcode model names inside the application.

The AI assistant should communicate through backend endpoints.

---

## Docker

Package the application using Docker.

The container should include:

- Frontend
- Backend
- SQLite database

Use:

uv

as the Python package manager.

Provide startup scripts for:

- Windows
- macOS
- Linux

inside:

scripts/

---

## Migration

The existing frontend currently uses dummy data.

Replace the dummy data with backend API calls.

Preserve the current UI and user experience during the migration.

Avoid unnecessary refactoring.

---

## Color Scheme

Accent Yellow:
#ecad0a

Blue Primary:
#209dd7

Purple Secondary:
#753991

Dark Navy:
#032147

Gray Text:
#888888

Preserve the existing design language.

---

## Development Workflow

For every major feature:

1. Read the relevant documentation.
2. Understand the existing implementation.
3. Plan the implementation.
4. Implement incrementally.
5. Test thoroughly.
6. Update documentation if necessary.

---

## Coding Standards

1. Use the latest stable libraries and modern best practices.
2. Keep the implementation as simple as possible.
3. Never over-engineer.
4. Always identify the root cause before fixing bugs.
5. Reuse existing code whenever possible.
6. Refactor only when necessary.
7. Keep documentation concise and accurate.
8. Keep the README minimal.
9. Never use emojis in project files.

---

## Important Rules

Treat this project as an evolution of an existing application.

Never rebuild functionality that already exists.

Reuse first.

Extend first.

Refactor only when necessary.

Preserve the existing UI unless new functionality requires changes.

Always understand the existing implementation before making modifications.