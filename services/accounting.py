# services/accounting.py
from fastapi import HTTPException
from typing import Dict, Any
from pydantic import UUID4
from supabase import create_client
import logging
from datetime import datetime
import os
from models.accounting import BalanceResponse, ChargeRequest, RefillRequest, Transaction, ReportResponse, AgentUsage

logger = logging.getLogger(__name__)

class AccountingService:
    def __init__(self):
        self.supabase = create_client(
            supabase_url=os.getenv("SUPABASE_URL"),
            supabase_key=os.getenv("SUPABASE_KEY")
        )

    async def get_balance(self, user_id: UUID4) -> BalanceResponse:
        """
        Get the current balance for a user based on their latest transaction.
        PERFORMANCE NOTE: This only retrieves the single most recent transaction.
        """
        try:
            # Performance-optimized query:
            # 1. Filter by user_id
            # 2. Order by timestamp DESC (newest first)
            # 3. Limit to only 1 row (most recent)
            result = self.supabase.table("agent_transactions")\
                .select("*")\
                .eq("user_id", str(user_id))\
                .order("timestamp", desc=True)\
                .limit(1)\
                .execute()

            if not result.data:
                # If no transactions found, return zero balance
                return BalanceResponse(
                    user_id=user_id,
                    balance=0,
                    timestamp=datetime.now()
                )

            transaction = result.data[0]
            return BalanceResponse(
                user_id=user_id,
                balance=transaction["balance"],
                timestamp=transaction["timestamp"]
            )
        except Exception as e:
            logger.error(f"Error getting balance: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to get balance: {str(e)}")

    async def charge_user(self, user_id: UUID4, charge_data: ChargeRequest) -> Transaction:
        """
        Charge credits from a user's balance for using an agent.
        This creates a transaction with type="run" and DECREASES the balance.
        """
        try:
            # Get current balance from the most recent transaction
            balance_response = await self.get_balance(user_id)
            current_balance = balance_response.balance

            # Check if user has enough credits
            if current_balance < charge_data.credits:
                raise HTTPException(
                    status_code=402,
                    detail=f"Insufficient credits. Current balance: {current_balance}, required: {charge_data.credits}"
                )

            # For charges (type="run"), we SUBTRACT credits from the balance
            new_balance = current_balance - charge_data.credits

            # Ensure agent_id is never null - it's required in the ChargeRequest model
            if not charge_data.agent_id:
                raise HTTPException(
                    status_code=400,
                    detail="agent_id is required for charging credits"
                )

            # Create transaction record with type="run" and DECREASED balance
            transaction_data = {
                "user_id": str(user_id),
                "agent_id": str(charge_data.agent_id),  # Convert UUID to string
                "run_id": str(charge_data.run_id) if charge_data.run_id else None,
                "type": "run",
                "credits": charge_data.credits,
                "balance": new_balance,
                "description": charge_data.description
            }

            # Log the transaction data for debugging
            logger.info(f"Creating charge transaction: {transaction_data}")

            # Insert transaction into database
            result = self.supabase.table("agent_transactions").insert(transaction_data).execute()

            if not result.data:
                raise HTTPException(status_code=500, detail="Failed to create transaction")

            # Log the result for debugging
            logger.info(f"Transaction result: {result.data[0]}")

            return Transaction.parse_obj(result.data[0])
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error charging user: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to charge user: {str(e)}")

    async def refill_user(self, user_id: UUID4, refill_data: RefillRequest) -> Transaction:
        """
        Add credits to a user's balance.
        This creates a transaction with type="refill" and INCREASES the balance.
        """
        try:
            # Get current balance from the most recent transaction
            balance_response = await self.get_balance(user_id)
            current_balance = balance_response.balance

            # For refills (type="refill"), we ADD credits to the balance
            new_balance = current_balance + refill_data.credits

            # Create transaction record with type="refill" and INCREASED balance
            transaction_data = {
                "user_id": str(user_id),
                "agent_id": None,  # Null for refill transactions
                "type": "refill",
                "credits": refill_data.credits,
                "balance": new_balance,
                "description": refill_data.description
            }

            # Insert transaction into database
            result = self.supabase.table("agent_transactions").insert(transaction_data).execute()

            if not result.data:
                raise HTTPException(status_code=500, detail="Failed to create refill transaction")

            return Transaction.parse_obj(result.data[0])
        except Exception as e:
            logger.error(f"Error refilling user: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to refill user: {str(e)}")

    async def get_report(self, user_id: UUID4, interval: str) -> ReportResponse:
        """
        Generate a usage report for the specified interval.
        """
        try:
            # Determine date range based on interval
            now = datetime.now()
            if interval == "day":
                start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
                end_date = now
            elif interval == "month":
                start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                end_date = now
            elif interval == "year":
                start_date = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
                end_date = now
            else:
                raise HTTPException(status_code=400, detail="Invalid interval. Must be 'day', 'month', or 'year'")

            # Get current balance for credits_remaining
            balance_response = await self.get_balance(user_id)
            current_balance = balance_response.balance

            # Get transactions for the interval
            result = self.supabase.table("agent_transactions")\
                .select("*")\
                .eq("user_id", str(user_id))\
                .eq("type", "run")\
                .gte("timestamp", start_date.isoformat())\
                .lte("timestamp", end_date.isoformat())\
                .execute()

            # Fetch agent information to get titles
            agent_ids = set()
            for transaction in result.data:
                if transaction["agent_id"]:
                    agent_ids.add(transaction["agent_id"])

            agent_titles = {}
            if agent_ids:
                # Fetch agent details from agents table
                agents_result = self.supabase.table("agents")\
                    .select("id,title")\
                    .in_("id", list(agent_ids))\
                    .execute()

                for agent in agents_result.data:
                    # Extract English title from the title JSON object
                    if agent["title"] and isinstance(agent["title"], dict) and "en" in agent["title"]:
                        agent_titles[agent["id"]] = agent["title"]["en"]
                    else:
                        agent_titles[agent["id"]] = f"Agent {agent['id'][:8]}"

            # Aggregate by agent_id
            agent_stats = {}
            total_credits = 0

            for transaction in result.data:
                agent_id = transaction["agent_id"]
                credits = transaction["credits"]
                run_id = transaction["run_id"]

                if agent_id not in agent_stats:
                    agent_stats[agent_id] = {
                        "total_credits": 0,
                        "runs": set()
                    }

                agent_stats[agent_id]["total_credits"] += credits
                total_credits += credits

                if run_id:
                    agent_stats[agent_id]["runs"].add(run_id)

            # Calculate final stats for each agent
            agents = []
            for agent_id, stats in agent_stats.items():
                run_count = len(stats["runs"])
                avg_credits = stats["total_credits"] / max(run_count, 1)  # Avoid division by zero

                # Get agent title if available
                agent_title = agent_titles.get(agent_id, f"Agent {agent_id[:8]}")

                agents.append(AgentUsage(
                    agent_id=UUID4(agent_id),
                    total_credits=stats["total_credits"],
                    run_count=run_count,
                    avg_credits_per_run=avg_credits,
                    agent_title_en=agent_title
                ))

            return ReportResponse(
                user_id=user_id,
                interval=interval,
                start_date=start_date,
                end_date=end_date,
                total_credits=total_credits,
                credits_remaining=current_balance,
                agents=agents
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error generating report: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to generate report: {str(e)}")