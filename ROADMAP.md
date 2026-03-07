Features to think about in no particular order.

- Database tools, being able to see and remove entries manually for debugging.
- Other logic to refresh the expiry timer for access if users had connected in the past 30 days.
- Added logic to prevent additional requests if the IP address has already been added.
- Creating the whole chatbot, webserver, database and firewall management into a docker compose for ease of setup
- Creating a discord channel for all of the chatbot log messages and create a message log role in discord
- Send Discord DM warning 3 days before expiration