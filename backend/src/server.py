from contextlib import asynccontextmanager
from datetime import datetime
import os
import sys

from bson import ObjectId
from fastapi import FastAPI, status
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel
import uvicorn

from dal import ToDoDAL, ListSummary, ToDoList

# Configuration
COLLECTION_NAME = "todo_lists"  # Name of the MongoDB collection
MONGODB_URI = os.environ["MONGODB_URI"]  # MongoDB connection URI from environment variables
DEBUG = os.environ.get("DEBUG", "").strip().lower() in {"1", "true", "on", "yes"}  # Debug mode flag

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages the lifespan of the FastAPI application,
    including the connection to the MongoDB database.

    Args:
        app (FastAPI): The FastAPI application instance.
    """
    # Startup:
    client = AsyncIOMotorClient(MONGODB_URI)  # Connect to MongoDB
    database = client.get_default_database()  # Get the default database

    # Ensure the database is available:
    pong = await database.command("ping")  # Ping the database to check connectivity
    if int(pong["ok"]) != 1:  # Check response
        raise Exception("Cluster connection is not okay!")

    todo_lists = database.get_collection(COLLECTION_NAME)  # Get the to-do lists collection
    app.todo_dal = ToDoDAL(todo_lists)  # Initialize the Data Access Layer

    # Yield back to FastAPI Application:
    yield  # Continue running the application

    # Shutdown:
    client.close()  # Close the database connection when shutting down

# Initialize FastAPI application with lifespan management and debug setting
app = FastAPI(lifespan=lifespan, debug=DEBUG)

@app.get("/api/lists")
async def get_all_lists() -> list[ListSummary]:
    """
    Endpoint to retrieve all to-do lists.
    
    Returns:
        list[ListSummary]: A list of summaries for all to-do lists.
    """
    return [i async for i in app.todo_dal.list_todo_lists()]  # Fetch and return all lists

class NewList(BaseModel):
    name: str  # Schema for creating a new list

class NewListResponse(BaseModel):
    id: str  # ID of the created list
    name: str  # Name of the created list

@app.post("/api/lists", status_code=status.HTTP_201_CREATED)
async def create_todo_list(new_list: NewList) -> NewListResponse:
    """
    Endpoint to create a new to-do list.
    
    Args:
        new_list (NewList): The data for the new list.
    
    Returns:
        NewListResponse: The response containing the ID and name of the created list.
    """
    return NewListResponse(
        id=await app.todo_dal.create_todo_list(new_list.name),  # Create the list and get its ID
        name=new_list.name,  # Return the name
    )

@app.get("/api/lists/{list_id}")
async def get_list(list_id: str) -> ToDoList:
    """
    Endpoint to retrieve a single to-do list by its ID.
    
    Args:
        list_id (str): The ID of the list to retrieve.
    
    Returns:
        ToDoList: The requested to-do list.
    """
    return await app.todo_dal.get_todo_list(list_id)  # Fetch and return the specified list

@app.delete("/api/lists/{list_id}")
async def delete_list(list_id: str) -> bool:
    """
    Endpoint to delete a to-do list by its ID.
    
    Args:
        list_id (str): The ID of the list to delete.
    
    Returns:
        bool: True if the list was deleted, False otherwise.
    """
    return await app.todo_dal.delete_todo_list(list_id)  # Attempt to delete the list

class NewItem(BaseModel):
    label: str  # Schema for creating a new item

class NewItemResponse(BaseModel):
    id: str  # ID of the created item
    label: str  # Label of the created item

@app.post(
    "/api/lists/{list_id}/items/",
    status_code=status.HTTP_201_CREATED,
)
async def create_item(list_id: str, new_item: NewItem) -> ToDoList:
    """
    Endpoint to add a new item to a specific to-do list.
    
    Args:
        list_id (str): The ID of the list to add the item to.
        new_item (NewItem): The data for the new item.
    
    Returns:
        ToDoList: The updated to-do list after adding the item.
    """
    return await app.todo_dal.create_item(list_id, new_item.label)  # Create the item and return the updated list

@app.delete("/api/lists/{list_id}/items/{item_id}")
async def delete_item(list_id: str, item_id: str) -> ToDoList:
    """
    Endpoint to delete a specific item from a to-do list.
    
    Args:
        list_id (str): The ID of the list.
        item_id (str): The ID of the item to delete.
    
    Returns:
        ToDoList: The updated to-do list after deleting the item.
    """
    return await app.todo_dal.delete_item(list_id, item_id)  # Delete the item and return the updated list

class ToDoItemUpdate(BaseModel):
    item_id: str  # ID of the item to update
    checked_state: bool  # New checked state for the item

@app.patch("/api/lists/{list_id}/checked_state")
async def set_checked_state(list_id: str, update: ToDoItemUpdate) -> ToDoList:
    """
    Endpoint to update the checked state of a specific item in a to-do list.
    
    Args:
        list_id (str): The ID of the list.
        update (ToDoItemUpdate): The update data for the item.
    
    Returns:
        ToDoList: The updated to-do list after changing the item's checked state.
    """
    return await app.todo_dal.set_checked_state(
        list_id, update.item_id, update.checked_state
    )  # Update the item's checked state and return the updated list

class DummyResponse(BaseModel):
    id: str  # ID of the dummy response
    when: datetime  # Timestamp of the dummy response

@app.get("/api/dummy")
async def get_dummy() -> DummyResponse:
    """
    Dummy endpoint for testing purposes.
    
    Returns:
        DummyResponse: A dummy response containing an ID and current timestamp.
    """
    return DummyResponse(
        id=str(ObjectId()),  # Generate a new ObjectId
        when=datetime.now(),  # Get the current datetime
    )

def main(argv=sys.argv[1:]):
    """
    Main entry point for running the FastAPI application.
    
    Args:
        argv (list): Command-line arguments.
    """
    try:
        uvicorn.run("server:app", host="0.0.0.0", port=3001, reload=DEBUG)  # Start the server
    except KeyboardInterrupt:
        pass  # Graceful exit on keyboard interrupt

if __name__ == "__main__":
    main()  # Run the main function if the script is executed directly
