from __future__ import annotations

import unittest

from luxury_price_ai.intake import build_auction_request_from_image_inspection
from luxury_price_ai.models import BrandCandidate, ImageInspectionResponse, ModelCandidate
from luxury_price_ai.tokens import extract_tokens


def inspection() -> ImageInspectionResponse:
    return ImageInspectionResponse(
        brand_candidates=[BrandCandidate(brand="CHANEL", confidence=0.98, evidence="logo")],
        model_candidates=[
            ModelCandidate(
                brand="CHANEL",
                model="CHANEL 22 Handbag IC Plate",
                confidence=0.86,
                evidence="CHANEL 22 style with chain and IC plate",
                distinguishing_features=["chain strap", "drawstring"],
            )
        ],
        condition_status="使用感あり",
        condition_confidence=0.78,
        visible_signals=["white and black handbag", "chain strap"],
        missing_photo_angles=[],
        warnings=[],
    )


class ImageAuctionMatchingTest(unittest.TestCase):
    def test_chanel_22_handbag_text_maps_to_model_and_shape(self) -> None:
        request = build_auction_request_from_image_inspection(
            inspection(),
            item_name="CHANEL 22 Handbag IC Plate",
        )

        self.assertEqual(request.brand, "CHANEL")
        self.assertEqual(request.shape, "ハンドバッグ")
        self.assertIsNone(request.rank)
        self.assertIn("CHANEL 22", request.title)
        self.assertIn("CHANEL 22", extract_tokens(request.title).models)


if __name__ == "__main__":
    unittest.main()
