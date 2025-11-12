File Vault – API Product

Requirements

Overview

Abnormal File Vault is a file hosting application designed to optimize storage efficiency and
enhance file retrieval through deduplication and intelligent search capabilities. The project
consists of a Django backend and API, containerized using Docker for easy setup and
deployment.

Business Case
As Abnormal AI continues to build AI-powered security solutions, efficient data storage and
retrieval are essential for managing files, reports, and forensic evidence related to cybersecurity
threats. A smart file management system like Abnormal File Vault could provide:
● Optimized Storage – Reducing redundancy through deduplication lowers storage costs
and improves performance.
● Faster Incident Investigations – A powerful search and filtering system enables
security teams to retrieve relevant files quickly.
● Scalability & Performance – Handling large datasets efficiently ensures seamless
operations as the system scales.
The ability to intelligently store, organize, and retrieve files aligns with Abnormal AI’s
mission to streamline and automate security workflows.

Technical Requirements
● Backend: Django/DRF
● Database: SQLite
● Containerization: Docker

Features & Functionality
Below features are to be added to existing starter project to fulfill the business need
1️File Deduplication System
Objective: Optimize storage efficiency by detecting and handling duplicate file uploads.
Requirements:
● Identify duplicate files during upload
● Store references to existing files instead of saving duplicates
● Provide a way to track and display storage savings (see API Contract)

2️Search & Filtering System
Objective: Enable efficient retrieval of stored files through search and filtering options.
Requirements:
● Add Query Parameters to the List Files API (for filtering/search):
● search: Search by filename (case-insensitive).
● file_type: Filter by MIME type (e.g., application/pdf).
● min_size, max_size: Filter by file size in bytes.
● start_date, end_date: Filter by upload date/time (ISO 8601 format).
● Allow multiple filters to be applied simultaneously
● Optimize search performance for large datasets

3 Call & Storage Limit Implementation
Objective: Protect the application’s health by programmatically limiting the number of
api calls a particular user can make per second and by limiting the amount of file
storage space used per user.

Requirements:
● Each API request should be traceable / trackable to a user. For simplicity, use a HTTP
Header called ‘UserId’ to pass in a userId

● API Calls by a particular user must be limited to ‘x’ calls per ’n’ seconds (Use 2 calls /
second for this exercise)
○ both ‘x’ and ’n’ values should be easily configured should changes be necessary
○ HTTP error code 429 with message “Call Limit Reached” should be returned if the call
limit has been reached
● Track the size of all files stored by each user
● Reject any file uploads that would exceed the user’s total storage limit ‘x’ Mb (Use 10Mb
per user for this exercise)
○ ‘x’ should be easily configured should changes be necessary
○ HTTP error code 429 with message “Storage Quota Exceeded” should be returned if
the storage limit has been reached

This document outlines the core functionality and business case for the project.

API Contract
GET /api/files/ - List Files
● Purpose: Retrieve a list of files for the authenticated user
● Authentication: Requires UserId header
● Query Parameters:
● search - Search by filename (case-insensitive partial match)
● file_type - Filter by MIME type (e.g., "text/plain", "image/jpeg")
● min_size / max_size - Filter by file size in bytes
● start_date / end_date - Filter by upload date (ISO 8601 format with timezone)
Response Format (200 OK):
{
"count": 2,
"next": null,
"previous": null,
"results": [

{
"id": "550e8400-e29b-41d4-a716-446655440000",
"file": "/media/uploads/550e8400-e29b-41d4-a716-446655440000.txt",
"original_filename": "document.txt",
"file_type": "text/plain",
"size": 1024,
"uploaded_at": "2024-01-15T10:30:00.123456Z",
"user_id": "user123",
"file_hash": "a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3",
"reference_count": 2,
"is_reference": false,
"original_file": null
},
{
"id": "550e8400-e29b-41d4-a716-446655440001",
"file": "/media/uploads/550e8400-e29b-41d4-a716-446655440000.txt",
"original_filename": "document_copy.txt",
"file_type": "text/plain",
"size": 1024,
"uploaded_at": "2024-01-15T11:00:00.456789Z",
"user_id": "user123",
"file_hash": "a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3",

"reference_count": 1,
"is_reference": true,
"original_file": "550e8400-e29b-41d4-a716-446655440000"
}
]
}

POST /api/files/ - Upload File
● Purpose: Upload a new file with automatic deduplication
● Authentication: Requires UserId header
● Request: Multipart form data with file field
● Features:
● Automatic file deduplication using SHA-256 hashing
● Creates references for duplicate files instead of storing multiple copies
● Updates storage usage statistics
● Enforces storage limits (10MB default per user)
Response Format (201 Created):
{
"id": "550e8400-e29b-41d4-a716-446655440000",
"file": "/media/uploads/550e8400-e29b-41d4-a716-446655440000.txt",
"original_filename": "uploaded_document.txt",
"file_type": "text/plain",
"size": 1024,
"uploaded_at": "2024-01-15T10:30:00.123456Z",

"user_id": "user123",
"file_hash": "a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3",
"reference_count": 1,
"is_reference": false,
"original_file": null
}

GET /api/files/{id}/ - Get File Details
● Purpose: Retrieve detailed information about a specific file
● Authentication: Requires UserId header
Response Format (200 OK):

{
"id": "550e8400-e29b-41d4-a716-446655440000",
"file": "/media/uploads/550e8400-e29b-41d4-a716-446655440000.txt",
"original_filename": "document.txt",
"file_type": "text/plain",
"size": 1024,
"uploaded_at": "2024-01-15T10:30:00.123456Z",
"user_id": "user123",
"file_hash": "a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3",
"reference_count": 1,

"is_reference": false,
"original_file": null
}

DELETE /api/files/{id}/ - Delete File
● Purpose: Delete a file and update storage usage
● Authentication: Requires UserId header
● Features:
● Handles reference counting for deduplicated files
● Updates storage usage statistics
● Only deletes actual file when no references remain
Response Format (204 No Content):

GET /api/files/storage_stats/ - Storage Statistics
● Purpose: Get storage usage statistics for the user
● Authentication: Requires UserId header
Field Descriptions:
● total_storage_used: Actual storage used (bytes) after deduplication
● original_storage_used: Storage that would be used (bytes) without deduplication
● storage_savings: Bytes saved through deduplication
● savings_percentage: Percentage of storage saved

Response Format (200 OK):
{
"user_id": "user123",

"total_storage_used": 5120,
"original_storage_used": 10240,
"storage_savings": 5120,
"savings_percentage": 50.0
}

GET /api/files/file_types/ - Available File Types
● Purpose: Get list of unique file types (MIME types) for the user
● Authentication: Requires UserId header
Response Format (200 OK):
[
"text/plain",
"image/jpeg",
"image/png",
"application/pdf",
"application/json"]
