"""
Memori Analytics - Theo dõi Sức khỏe & Sử dụng Bộ nhớ.
Phase 4: Analytics cho phép giám sát và tối ưu hóa.

Tính năng:
- Tính điểm sức khỏe bộ nhớ (Memory health score)
- Phân tích sử dụng và thống kê
- Số liệu chất lượng (Quality metrics)
- Đề xuất cải thiện
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from uuid import UUID

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class MemoriAnalytics:
    """
    Hệ thống Analytics cho quản lý bộ nhớ Memori.
    Phase 4: Cung cấp thông tin chi tiết về chất lượng và mức sử dụng bộ nhớ.
    """
    
    def __init__(self, session: AsyncSession):
        """
        Khởi tạo hệ thống analytics.
        
        Args:
            session: Database session
        """
        self.session = session
    
    async def get_memory_health_score(
        self,
        entity_id: str,
        workspace_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """
        Tính điểm sức khỏe bộ nhớ toàn diện cho một entity.
        
        Các thành phần điểm Sức khỏe:
        1. Coverage (30%): Bao nhiêu thông tin đưc lưu trữ
        2. Quality (30%): Độ quan trọng trung bình của facts
        3. Freshness (20%): Mức độ mới của facts
        4. Diversity (20%): Sự đa dạng của các loại facts
        
        Args:
            entity_id: External entity ID
            workspace_id: Bộ lọc workspace tùy chọn
            
        Returns:
            Dict chứa điểm sức khỏe và chi tiết phân tích
        """
        from app.db.models import (
            MemoriEntity,
            MemoriEntityFact,
            MemoriEntityPreference,
            MemoriEntityAttribute,
            MemoriKnowledgeGraph,
        )
        
        try:
            # Lấy internal entity ID
            result = await self.session.execute(
                select(MemoriEntity.id).where(MemoriEntity.external_id == entity_id)
            )
            internal_id = result.scalar_one_or_none()
            
            if not internal_id:
                return {
                    "entity_id": entity_id,
                    "health_score": 0.0,
                    "status": "no_data",
                    "message": "Không tìm thấy dữ liệu bộ nhớ cho entity này",
                }
            
            # 1. Coverage Score (30%)
            coverage_score = await self._calculate_coverage_score(internal_id)
            
            # 2. Quality Score (30%)
            quality_score = await self._calculate_quality_score(internal_id)
            
            # 3. Freshness Score (20%)
            freshness_score = await self._calculate_freshness_score(internal_id)
            
            # 4. Diversity Score (20%)
            diversity_score = await self._calculate_diversity_score(internal_id)
            
            # Tính điểm sức khỏe có trọng số
            health_score = (
                coverage_score * 0.30 +
                quality_score * 0.30 +
                freshness_score * 0.20 +
                diversity_score * 0.20
            )
            
            # Xác định trạng thái
            if health_score >= 0.8:
                status = "excellent"
            elif health_score >= 0.6:
                status = "good"
            elif health_score >= 0.4:
                status = "fair"
            else:
                status = "poor"
            
            return {
                "entity_id": entity_id,
                "health_score": round(health_score, 3),
                "status": status,
                "breakdown": {
                    "coverage": round(coverage_score, 3),
                    "quality": round(quality_score, 3),
                    "freshness": round(freshness_score, 3),
                    "diversity": round(diversity_score, 3),
                },
                "recommendations": self._generate_recommendations(
                    coverage_score,
                    quality_score,
                    freshness_score,
                    diversity_score,
                ),
            }
        except Exception as e:
            logger.error(f"Tính điểm sức khỏe thất bại: {e}")
            return {
                "entity_id": entity_id,
                "health_score": 0.0,
                "status": "error",
                "message": str(e),
            }
    
    async def _calculate_coverage_score(self, entity_id: int) -> float:
        """
        Tính điểm độ bao phủ dựa trên lượng thông tin được lưu trữ.
        
        Cách tính điểm:
        - 0-10 facts: 0.0-0.3
        - 10-50 facts: 0.3-0.7
        - 50+ facts: 0.7-1.0
        """
        from app.db.models import MemoriEntityFact
        
        result = await self.session.execute(
            select(func.count(MemoriEntityFact.id))
            .where(MemoriEntityFact.entity_id == entity_id)
        )
        fact_count = result.scalar() or 0
        
        if fact_count == 0:
            return 0.0
        elif fact_count < 10:
            return 0.3 * (fact_count / 10.0)
        elif fact_count < 50:
            return 0.3 + 0.4 * ((fact_count - 10) / 40.0)
        else:
            return min(1.0, 0.7 + 0.3 * ((fact_count - 50) / 100.0))
    
    async def _calculate_quality_score(self, entity_id: int) -> float:
        """
        Tính điểm chất lượng dựa trên độ quan trọng trung bình của facts.
        
        Cách tính điểm:
        - Avg importance 0-3: 0.0-0.3
        - Avg importance 3-7: 0.3-0.7
        - Avg importance 7-10: 0.7-1.0
        """
        from app.db.models import MemoriEntityFact
        
        result = await self.session.execute(
            select(func.avg(MemoriEntityFact.importance_score))
            .where(MemoriEntityFact.entity_id == entity_id)
        )
        avg_importance = result.scalar() or 0.0
        
        if avg_importance < 3.0:
            return avg_importance / 10.0
        elif avg_importance < 7.0:
            return 0.3 + 0.4 * ((avg_importance - 3.0) / 4.0)
        else:
            return 0.7 + 0.3 * ((avg_importance - 7.0) / 3.0)
    
    async def _calculate_freshness_score(self, entity_id: int) -> float:
        """
        Tính điểm độ mới dựa trên thời gian gần đây của facts.
        
        Cách tính điểm:
        - Facts từ 7 ngày qua: 1.0
        - Facts từ 30 ngày qua: 0.7
        - Facts từ 90 ngày qua: 0.4
        - Facts cũ hơn: 0.0-0.4
        """
        from app.db.models import MemoriEntityFact
        
        now = datetime.now(timezone.utc)  # Sử dụng timezone-aware datetime
        
        # Lấy fact mới nhất
        result = await self.session.execute(
            select(func.max(MemoriEntityFact.created_at))
            .where(MemoriEntityFact.entity_id == entity_id)
        )
        most_recent = result.scalar()
        
        if not most_recent:
            return 0.0
        
        # Đảm bảo most_recent là timezone-aware
        if most_recent.tzinfo is None:
            import pytz
            most_recent = pytz.utc.localize(most_recent)
        
        days_old = (now - most_recent).days
        
        if days_old <= 7:
            return 1.0
        elif days_old <= 30:
            return 0.7 + 0.3 * (1.0 - (days_old - 7) / 23.0)
        elif days_old <= 90:
            return 0.4 + 0.3 * (1.0 - (days_old - 30) / 60.0)
        else:
            return max(0.0, 0.4 * (1.0 - (days_old - 90) / 180.0))
    
    async def _calculate_diversity_score(self, entity_id: int) -> float:
        """
        Tính điểm đa dạng dựa trên sự đa dạng của các loại memory.
        
        Cách tính điểm:
        - Chỉ có facts: 0.4
        - Có facts + preferences: 0.6
        - Có facts + attributes: 0.6
        - Có facts + knowledge graph: 0.7
        - Có tất cả các loại: 1.0
        """
        from app.db.models import (
            MemoriEntityFact,
            MemoriEntityPreference,
            MemoriEntityAttribute,
            MemoriKnowledgeGraph,
        )
        
        # Kiểm tra từng loại memory
        has_facts = await self._has_records(MemoriEntityFact, entity_id)
        has_preferences = await self._has_records(MemoriEntityPreference, entity_id)
        has_attributes = await self._has_records(MemoriEntityAttribute, entity_id)
        has_kg = await self._has_records(MemoriKnowledgeGraph, entity_id)
        
        type_count = sum([has_facts, has_preferences, has_attributes, has_kg])
        
        if type_count == 0:
            return 0.0
        elif type_count == 1:
            return 0.4
        elif type_count == 2:
            return 0.6
        elif type_count == 3:
            return 0.8
        else:
            return 1.0
    
    async def _has_records(self, model, entity_id: int) -> bool:
        """Kiểm tra xem entity có bản ghi nào thuộc loại đã cho không."""
        result = await self.session.execute(
            select(func.count(model.id))
            .where(model.entity_id == entity_id)
        )
        count = result.scalar() or 0
        return count > 0
    
    def _generate_recommendations(
        self,
        coverage: float,
        quality: float,
        freshness: float,
        diversity: float,
    ) -> List[str]:
        """Tạo đề xuất dựa trên chi tiết điểm số."""
        recommendations = []
        
        if coverage < 0.5:
            recommendations.append(
                "Độ bao phủ thấp: Khuyến khích thêm các cuộc hội thoại để trích xuất nhiều facts hơn"
            )
        
        if quality < 0.5:
            recommendations.append(
                "Chất lượng thấp: Tập trung trích xuất các facts có độ quan trọng cao"
            )
        
        if freshness < 0.5:
            recommendations.append(
                "Dữ liệu cũ: Các tương tác gần đây sẽ cải thiện độ mới của bộ nhớ"
            )
        
        if diversity < 0.6:
            recommendations.append(
                "Đa dạng thấp: Trích xuất thêm preferences và attributes để ngữ cảnh phong phú hơn"
            )
        
        if not recommendations:
            recommendations.append("Sức khỏe bộ nhớ tốt! Tiếp tục duy trì tương tác.")
        
        return recommendations
    
    async def get_usage_analytics(
        self,
        entity_id: str,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        Lấy thống kê sử dụng cho một entity trong khoảng thời gian cụ thể.
        
        Args:
            entity_id: External entity ID
            days: Số ngày phân tích
            
        Returns:
            Dict chứa thống kê sử dụng
        """
        from app.db.models import (
            MemoriEntity,
            MemoriEntityFact,
            MemoriEntityPreference,
            MemoriEntityAttribute,
        )
        
        try:
            # Lấy internal entity ID
            result = await self.session.execute(
                select(MemoriEntity.id).where(MemoriEntity.external_id == entity_id)
            )
            internal_id = result.scalar_one_or_none()
            
            if not internal_id:
                return {
                    "entity_id": entity_id,
                    "message": "Không tìm thấy dữ liệu",
                }
            
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
            
            # Facts được thêm trong khoảng thời gian
            facts_result = await self.session.execute(
                select(func.count(MemoriEntityFact.id))
                .where(
                    and_(
                        MemoriEntityFact.entity_id == internal_id,
                        MemoriEntityFact.created_at >= cutoff_date,
                    )
                )
            )
            facts_added = facts_result.scalar() or 0
            
            # Facts được truy cập trong khoảng thời gian
            accessed_result = await self.session.execute(
                select(func.count(MemoriEntityFact.id))
                .where(
                    and_(
                        MemoriEntityFact.entity_id == internal_id,
                        MemoriEntityFact.last_accessed_at >= cutoff_date,
                    )
                )
            )
            facts_accessed = accessed_result.scalar() or 0
            
            # Tổng số facts
            total_result = await self.session.execute(
                select(func.count(MemoriEntityFact.id))
                .where(MemoriEntityFact.entity_id == internal_id)
            )
            total_facts = total_result.scalar() or 0
            
            # Số lượng preferences
            prefs_result = await self.session.execute(
                select(func.count(MemoriEntityPreference.id))
                .where(MemoriEntityPreference.entity_id == internal_id)
            )
            total_preferences = prefs_result.scalar() or 0
            
            # Số lượng attributes
            attrs_result = await self.session.execute(
                select(func.count(MemoriEntityAttribute.id))
                .where(MemoriEntityAttribute.entity_id == internal_id)
            )
            total_attributes = attrs_result.scalar() or 0
            
            # Tính toán metrics
            access_rate = (facts_accessed / total_facts * 100) if total_facts > 0 else 0
            growth_rate = (facts_added / max(1, total_facts - facts_added) * 100)
            
            return {
                "entity_id": entity_id,
                "period_days": days,
                "facts": {
                    "total": total_facts,
                    "added_in_period": facts_added,
                    "accessed_in_period": facts_accessed,
                    "access_rate_percent": round(access_rate, 1),
                    "growth_rate_percent": round(growth_rate, 1),
                },
                "preferences": {
                    "total": total_preferences,
                },
                "attributes": {
                    "total": total_attributes,
                },
                "summary": {
                    "total_memories": total_facts + total_preferences + total_attributes,
                    "activity_level": self._classify_activity(facts_added, facts_accessed),
                },
            }
        except Exception as e:
            logger.error(f"Lấy thống kê sử dụng thất bại: {e}")
            return {
                "entity_id": entity_id,
                "error": str(e),
            }
    
    def _classify_activity(self, facts_added: int, facts_accessed: int) -> str:
        """Phân loại mức độ hoạt động dựa trên số lượng thêm và truy cập."""
        total_activity = facts_added + facts_accessed
        
        if total_activity >= 50:
            return "very_active"
        elif total_activity >= 20:
            return "active"
        elif total_activity >= 5:
            return "moderate"
        elif total_activity > 0:
            return "low"
        else:
            return "inactive"
    
    async def get_top_facts(
        self,
        entity_id: str,
        limit: int = 10,
        sort_by: str = "importance",
    ) -> List[Dict[str, Any]]:
        """
        Lấy các facts hàng đầu của entity.
        
        Args:
            entity_id: External entity ID
            limit: Số lượng facts trả về
            sort_by: Tiêu chí sắp xếp ("importance", "recent", "accessed")
            
        Returns:
            Danh sách top facts kèm metadata
        """
        from app.db.models import MemoriEntity, MemoriEntityFact
        
        try:
            # Lấy internal entity ID
            result = await self.session.execute(
                select(MemoriEntity.id).where(MemoriEntity.external_id == entity_id)
            )
            internal_id = result.scalar_one_or_none()
            
            if not internal_id:
                return []
            
            # Build query dựa trên tiêu chí sort
            query = select(MemoriEntityFact).where(
                MemoriEntityFact.entity_id == internal_id
            )
            
            if sort_by == "importance":
                query = query.order_by(MemoriEntityFact.importance_score.desc())
            elif sort_by == "recent":
                query = query.order_by(MemoriEntityFact.created_at.desc())
            elif sort_by == "accessed":
                query = query.order_by(MemoriEntityFact.last_accessed_at.desc())
            
            query = query.limit(limit)
            
            result = await self.session.execute(query)
            facts = result.scalars().all()
            
            return [
                {
                    "id": f.id,
                    "content": f.content,
                    "importance_score": f.importance_score or 1.0,
                    "created_at": f.created_at.isoformat() if f.created_at else None,
                    "last_accessed_at": f.last_accessed_at.isoformat() if f.last_accessed_at else None,
                }
                for f in facts
            ]
        except Exception as e:
            logger.error(f"Lấy top facts thất bại: {e}")
            return []
