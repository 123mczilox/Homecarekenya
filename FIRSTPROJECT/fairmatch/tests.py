import unittest

from fairmatch.engine import recommend_allocations, rank_needs


class FairMatchTests(unittest.TestCase):
    def _need(self, **kwargs):
        base = {
            "need_id": 1,
            "home_id": 10,
            "resource_type": "maize flour",
            "quantity_requested": 50,
            "quantity_fulfilled": 0,
            "urgency": 5,
            "deadline": "2026-10-30",
            "verification_status": "verified",
            "delivery_feasible": True,
            "storage_capacity_available": True,
            "unit": "kg",
        }
        base.update(kwargs)
        return base

    def _offer(self, **kwargs):
        base = {
            "resource_id": 100,
            "donor_id": 25,
            "resource_type": "maize flour",
            "quantity_available": 100,
            "unit": "kg",
            "expiry_date": None,
            "collection_location": "Nairobi",
            "available_until": "2026-10-30",
            "safety_status": "approved",
            "availability_status": "available",
        }
        base.update(kwargs)
        return base

    def test_urgent_need_ranked_higher(self):
        urgent = self._need(need_id=1, home_id=10, urgency=5)
        normal = self._need(need_id=2, home_id=11, urgency=2, quantity_requested=40)
        offer = self._offer(quantity_available=100)

        ranked = rank_needs([urgent, normal], offer)
        self.assertEqual(ranked[0]["need_id"], 1)

    def test_partial_fulfilment_is_respected(self):
        need = self._need(quantity_requested=100, quantity_fulfilled=70)
        offer = self._offer(quantity_available=100)

        result = recommend_allocations([need], offer)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["recommended_quantity"], 30)

    def test_insufficient_supply_is_not_exceeded(self):
        need_a = self._need(need_id=1, home_id=10, quantity_requested=50)
        need_b = self._need(need_id=2, home_id=11, quantity_requested=30)
        offer = self._offer(quantity_available=50)

        result = recommend_allocations([need_a, need_b], offer)
        total = sum(item["recommended_quantity"] for item in result)
        self.assertLessEqual(total, 50)

    def test_resource_incompatibility_is_excluded(self):
        need = self._need(resource_type="maize flour")
        offer = self._offer(resource_type="cooking oil")

        ranked = rank_needs([need], offer)
        self.assertEqual(ranked, [])

    def test_unsafe_or_expired_offer_is_excluded(self):
        need = self._need()
        offer = self._offer(safety_status="rejected", quantity_available=10)

        ranked = rank_needs([need], offer)
        self.assertEqual(ranked, [])

    def test_duplicate_allocation_prevention(self):
        need = self._need(need_id=1, home_id=10, quantity_requested=50)
        offer = self._offer(resource_id=100, quantity_available=60)
        allocation_history = [{"resource_id": 100, "need_id": 1, "home_id": 10, "quantity_allocated": 20}]

        result = recommend_allocations([need], offer, allocation_history)
        self.assertEqual(result[0]["recommended_quantity"], 30)

    def test_fairness_rule_reduces_score_for_recent_assistance(self):
        first = self._need(need_id=1, home_id=10, quantity_requested=40, urgency=5)
        second = self._need(need_id=2, home_id=11, quantity_requested=40, urgency=5)
        offer = self._offer(quantity_available=70)
        history = [{"home_id": 10, "quantity_allocated": 50, "resource_id": 100}]

        ranked = rank_needs([first, second], offer, history)
        self.assertLess(ranked[1]["priority_score"], ranked[0]["priority_score"])

    def test_missing_or_invalid_data_fails_safely(self):
        invalid = self._need(quantity_requested=0, urgency="invalid")
        offer = self._offer(quantity_available=50)

        ranked = rank_needs([invalid], offer)
        self.assertEqual(ranked, [])

    def test_no_eligible_candidates_returns_empty_list(self):
        need = self._need(verification_status="pending")
        offer = self._offer(quantity_available=50)

        ranked = rank_needs([need], offer)
        self.assertEqual(ranked, [])

    def test_deterministic_results(self):
        need_a = self._need(need_id=1, home_id=10, urgency=4)
        need_b = self._need(need_id=2, home_id=11, urgency=4)
        offer = self._offer(quantity_available=100)

        first = rank_needs([need_a, need_b], offer)
        second = rank_needs([need_a, need_b], offer)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
