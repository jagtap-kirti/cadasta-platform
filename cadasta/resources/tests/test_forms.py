import pytest
from django.test import TestCase

from core.tests.utils.cases import UserTestCase, FileStorageTestCase
from core.tests.utils.files import make_dirs  # noqa
from accounts.tests.factories import UserFactory
from organization.tests.factories import ProjectFactory
from ..forms import ResourceForm, AddResourceFromLibraryForm
from .factories import ResourceFactory
from .utils import clear_temp  # noqa


@pytest.mark.usefixtures('make_dirs')
@pytest.mark.usefixtures('clear_temp')
class ResourceFormTest(UserTestCase, FileStorageTestCase, TestCase):
    def setUp(self):
        super().setUp()
        file = self.get_file('/resources/tests/files/image.jpg', 'rb')
        file_name = self.storage.save('resources/image.jpg', file.read())
        file.close()

        self.data = {
            'name': 'Some name',
            'description': '',
            'file': file_name,
            'original_file': 'image.jpg',
            'mime_type': 'image/jpeg'
        }
        self.project = ProjectFactory.create()

    def test_create_resource(self):
        user = UserFactory.create()
        form = ResourceForm(self.data,
                            content_object=self.project,
                            contributor=user,
                            project_id=self.project.id)
        assert form.is_valid() is True
        form.save()
        assert self.project.resources.count() == 1
        assert self.project.resources.first().name == self.data['name']
        assert self.project.resources.first().contributor == user

    def test_update_resource(self):
        user = UserFactory.create()
        resource = ResourceFactory(content_object=self.project,
                                   project=self.project)
        form = ResourceForm(self.data,
                            instance=resource,
                            contributor=user)

        assert form.is_valid() is True
        form.save()
        assert self.project.resources.count() == 1
        assert self.project.resources.first().name == self.data['name']
        assert self.project.resources.first().contributor == user

    def test_string_sanitation(self):
        user = UserFactory.create()
        data = self.data.copy()
        data['name'] = '<name>'
        form = ResourceForm(data,
                            content_object=self.project,
                            contributor=user,
                            project_id=self.project.id)
        assert form.is_valid() is False
        assert form.errors['name'] is not None


@pytest.mark.usefixtures('make_dirs')
class AddResourceFromLibraryFormTest(UserTestCase, TestCase):
    def test_init(self):
        prj = ProjectFactory.create()
        ResourceFactory.create(project=prj, content_object=prj)
        res = ResourceFactory.create(project=prj)

        form = AddResourceFromLibraryForm(project_id=prj.id,
                                          content_object=prj)
        assert len(form.fields) == 1
        assert form.fields[res.id].initial is False

    def test_save(self):
        prj = ProjectFactory.create()
        prj_res = ResourceFactory.create(project=prj, content_object=prj)
        res = ResourceFactory.create(project=prj)

        data = {
            res.id: 'on'
        }

        form = AddResourceFromLibraryForm(data=data,
                                          project_id=prj.id,
                                          content_object=prj)

        assert form.is_valid() is True
        form.save()

        assert prj.resources.count() == 2
        assert res in prj.resources
        assert prj_res in prj.resources
