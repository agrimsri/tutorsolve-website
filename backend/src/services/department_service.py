from flask import current_app


class DepartmentService:

    @staticmethod
    def get_all_departments():
        departments = current_app.mongo.departments

        cursor = departments.find({"active": True}).sort("name", 1)

        result = []
        for dept in cursor:
            result.append({
                "slug": dept.get("slug"),
                "name": dept.get("name")
            })

        return result

    @staticmethod
    def is_valid_department(slug: str):
        departments = current_app.mongo.departments
        return departments.find_one({"slug": slug, "active": True}) is not None
