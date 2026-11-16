# Privacy and local storage

Manual models, local source inventories, temporary calculation snapshots and clipboard screenshots are processed on the local machine. Sending a chat request discloses the reviewed selected sources/images, question/history and included workspace contents to the chosen provider account/model. Provider terms and workspace policy apply.

Review every outgoing manifest. Include current workspace model sends its model content. Include saved source inventory is off by default and adds embedded evidence only after opt-in. A saved `.amua` file may contain notes, source inventory and quoted values; review before sharing. Save shareable copy removes embedded inventory/quoted input-review evidence while retaining executable values, notes, source labels and unresolved guards. It is not an anonymization guarantee.

3.2.4 uses `~/Library/Application Support/Amua-v3.2.4`. Pasted images are stored with owner-only permissions under `chat-attachments`, bounded to 100 MiB. Clearing attachments removes the selection and cancels a pending paste, but retained PNGs remain for source provenance. Remove unused local images deliberately when no longer needed. Ordinary file attachments retain original paths; moving them requires renewed inspection.

ChatGPT connection secrets use the compatible OS credential store. The app's support state includes account/registration metadata and logs; do not upload it wholesale. No account files, credentials or user workspace are included in this repository or installer. The bridge token is local to the running version. No telemetry or unattended cloud upload is installed by this packaging workflow.

Use synthetic or appropriately de-identified data for public issues and examples. Do not post patient data, tokens, passwords, browser authorization codes or confidential source documents. See [Security](../SECURITY.md) for reporting.
