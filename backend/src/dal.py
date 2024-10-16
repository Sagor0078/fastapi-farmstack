from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorCollection
from pymongo import ReturnDocument

from pydantic import BaseModel

from uuid import uuid4


class ListSummary(BaseModel):
    id: str  # Unique identifier for the list
    name: str  # Name of the to-do list
    item_count: int  # Count of items in the list

    @staticmethod
    def from_doc(doc) -> "ListSummary":
        """
        Creates a ListSummary instance from a MongoDB document.
        
        Args:
            doc: The MongoDB document to convert.
        
        Returns:
            ListSummary: An instance of ListSummary.
        """
        return ListSummary(
            id=str(doc["_id"]),  # Convert ObjectId to string
            name=doc["name"],  # Extract name from the document
            item_count=doc["item_count"],  # Extract item count
        )


class ToDoListItem(BaseModel):
    id: str  # Unique identifier for the to-do list item
    label: str  # Description of the item
    checked: bool  # Whether the item is completed

    @staticmethod
    def from_doc(item) -> "ToDoListItem":
        """
        Creates a ToDoListItem instance from a MongoDB document.
        
        Args:
            item: The MongoDB document representing a to-do list item.
        
        Returns:
            ToDoListItem: An instance of ToDoListItem.
        """
        return ToDoListItem(
            id=item["id"],  # Extract id from the document
            label=item["label"],  # Extract label
            checked=item["checked"],  # Extract checked state
        )


class ToDoList(BaseModel):
    id: str  # Unique identifier for the to-do list
    name: str  # Name of the to-do list
    items: list[ToDoListItem]  # List of items in the to-do list

    @staticmethod
    def from_doc(doc) -> "ToDoList":
        """
        Creates a ToDoList instance from a MongoDB document.
        
        Args:
            doc: The MongoDB document to convert.
        
        Returns:
            ToDoList: An instance of ToDoList.
        """
        return ToDoList(
            id=str(doc["_id"]),  # Convert ObjectId to string
            name=doc["name"],  # Extract name
            items=[ToDoListItem.from_doc(item) for item in doc["items"]],  # Convert items to ToDoListItem instances
        )


class ToDoDAL:
    def __init__(self, todo_collection: AsyncIOMotorCollection):
        """
        Initializes the ToDoDAL with a MongoDB collection.
        
        Args:
            todo_collection: The MongoDB collection to operate on.
        """
        self._todo_collection = todo_collection

    async def list_todo_lists(self, session=None):
        """
        Retrieves all to-do lists from the collection.
        
        Args:
            session: Optional MongoDB session.
        
        Yields:
            ListSummary: A summary of each to-do list.
        """
        async for doc in self._todo_collection.find(
            {},
            projection={
                "name": 1,
                "item_count": {"$size": "$items"},  # Count items in the list
            },
            sort={"name": 1},  # Sort by name
            session=session,
        ):
            yield ListSummary.from_doc(doc)  # Convert each document to ListSummary

    async def create_todo_list(self, name: str, session=None) -> str:
        """
        Creates a new to-do list.
        
        Args:
            name: The name of the new to-do list.
            session: Optional MongoDB session.
        
        Returns:
            str: The ID of the newly created to-do list.
        """
        response = await self._todo_collection.insert_one(
            {"name": name, "items": []},  # Initialize with an empty items list
            session=session,
        )
        return str(response.inserted_id)  # Return the inserted ID as a string

    async def get_todo_list(self, id: str | ObjectId, session=None) -> ToDoList:
        """
        Retrieves a specific to-do list by its ID.
        
        Args:
            id: The ID of the to-do list to retrieve.
            session: Optional MongoDB session.
        
        Returns:
            ToDoList: The retrieved to-do list.
        """
        doc = await self._todo_collection.find_one(
            {"_id": ObjectId(id)},  # Find by ObjectId
            session=session,
        )
        return ToDoList.from_doc(doc)  # Convert to ToDoList instance

    async def delete_todo_list(self, id: str | ObjectId, session=None) -> bool:
        """
        Deletes a to-do list by its ID.
        
        Args:
            id: The ID of the to-do list to delete.
            session: Optional MongoDB session.
        
        Returns:
            bool: True if the list was deleted, False otherwise.
        """
        response = await self._todo_collection.delete_one(
            {"_id": ObjectId(id)},  # Find by ObjectId
            session=session,
        )
        return response.deleted_count == 1  # Return True if one document was deleted

    async def create_item(
        self,
        id: str | ObjectId,
        label: str,
        session=None,
    ) -> ToDoList | None:
        """
        Adds a new item to a specific to-do list.
        
        Args:
            id: The ID of the to-do list to add the item to.
            label: The label of the new item.
            session: Optional MongoDB session.
        
        Returns:
            ToDoList: The updated to-do list, or None if not found.
        """
        result = await self._todo_collection.find_one_and_update(
            {"_id": ObjectId(id)},  # Find the list by ID
            {
                "$push": {
                    "items": {
                        "id": uuid4().hex,  # Generate a unique ID for the item
                        "label": label,  # Set the label
                        "checked": False,  # Initialize checked state to False
                    }
                }
            },
            session=session,
            return_document=ReturnDocument.AFTER,  # Return the updated document
        )
        if result:
            return ToDoList.from_doc(result)  # Convert to ToDoList instance

    async def set_checked_state(
        self,
        doc_id: str | ObjectId,
        item_id: str,
        checked_state: bool,
        session=None,
    ) -> ToDoList | None:
        """
        Updates the checked state of a specific item in a to-do list.
        
        Args:
            doc_id: The ID of the to-do list.
            item_id: The ID of the item to update.
            checked_state: The new checked state (True or False).
            session: Optional MongoDB session.
        
        Returns:
            ToDoList: The updated to-do list, or None if not found.
        """
        result = await self._todo_collection.find_one_and_update(
            {"_id": ObjectId(doc_id), "items.id": item_id},  # Find by list ID and item ID
            {"$set": {"items.$.checked": checked_state}},  # Update the checked state
            session=session,
            return_document=ReturnDocument.AFTER,  # Return the updated document
        )
        if result:
            return ToDoList.from_doc(result)  # Convert to ToDoList instance

    async def delete_item(
        self,
        doc_id: str | ObjectId,
        item_id: str,
        session=None,
    ) -> ToDoList | None:
        """
        Deletes a specific item from a to-do list.
        
        Args:
            doc_id: The ID of the to-do list.
            item_id: The ID of the item to delete.
            session: Optional MongoDB session.
        
        Returns:
            ToDoList: The updated to-do list, or None if not found.
        """
        result = await self._todo_collection.find_one_and_update(
            {"_id": ObjectId(doc_id)},  # Find the list by ID
            {"$pull": {"items": {"id": item_id}}},  # Remove the item by its ID
            session=session,
            return_document=ReturnDocument.AFTER,  # Return the updated document
        )
        if result:
            return ToDoList.from_doc(result)  # Convert to ToDoList instance
