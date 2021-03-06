from core.tests.utils.cases import UserTestCase
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from jsonattrs.models import Attribute, AttributeType, Schema
from organization.tests.factories import ProjectFactory
from party.tests.factories import PartyFactory
from questionnaires.tests import factories as q_factories

from .. import forms
from ..models import Party
from ..choices import TENURE_RELATIONSHIP_TYPES


class PartyFormTest(UserTestCase, TestCase):

    def test_init_without_questionnaire(self):
        project = ProjectFactory.create()
        form = forms.PartyForm(project)
        assert hasattr(form.fields['name'], 'labels_xlang') is False
        assert hasattr(form.fields['type'], 'labels_xlang') is False

    def test_init_with_questionnaire(self):
        project = ProjectFactory.create()
        questionnaire = q_factories.QuestionnaireFactory(project=project)
        q_factories.QuestionFactory.create(
            name='party_type',
            questionnaire=questionnaire,
            label={'en': 'Type', 'de': 'Typ'})
        q_factories.QuestionFactory.create(
            name='party_name',
            questionnaire=questionnaire,
            label={'en': 'Name', 'de': 'Name'})
        form = forms.PartyForm(project)
        assert hasattr(form.fields['name'], 'labels_xlang') is True
        assert hasattr(form.fields['type'], 'labels_xlang') is True

    def test_create_party(self):
        data = {
            'name': 'Cadasta',
            'type': 'IN'
        }
        project = ProjectFactory.create()
        form = forms.PartyForm(project, data=data)
        form.is_valid()
        form.save()

        assert Party.objects.filter(project=project).count() == 1

    def test_create_party_with_attributes(self):
        data = {
            'name': 'Cadasta',
            'type': 'IN',
            'party::in::fname': 'test',
            'party::in::homeowner': 'true',
            'party::in::age': 35
        }
        project = ProjectFactory.create()

        content_type = ContentType.objects.get(
            app_label='party', model='party')
        schema = Schema.objects.create(
            content_type=content_type,
            selectors=(project.organization.id, project.id, ))

        Attribute.objects.create(
            schema=schema,
            name='fname',
            long_name='Test field',
            attr_type=AttributeType.objects.get(name='text'),
            index=0
        )
        Attribute.objects.create(
            schema=schema,
            name='homeowner',
            long_name='Homeowner',
            attr_type=AttributeType.objects.get(name='boolean'),
            index=1
        )
        Attribute.objects.create(
            schema=schema,
            name='age',
            long_name='Homeowner Age',
            attr_type=AttributeType.objects.get(name='integer'),
            index=2, required=True, default=0
        )

        form = forms.PartyForm(project=project, data=data)
        form.is_valid()
        form.save()

        assert Party.objects.filter(project=project).count() == 1
        party = Party.objects.filter(project=project).first()
        assert party.attributes.get('fname') == 'test'
        assert party.attributes.get('homeowner')
        assert party.attributes.get('age') == 35

    def test_edit_party_with_attributes(self):
        data = {
            'name': 'Cadasta',
            'type': 'IN',
            'party::in::fname': 'updated value',
            'party::in::age': 37
        }
        project = ProjectFactory.create()

        content_type = ContentType.objects.get(
            app_label='party', model='party')
        schema = Schema.objects.create(
            content_type=content_type,
            selectors=(project.organization.id, project.id, ))

        Attribute.objects.create(
            schema=schema,
            name='fname',
            long_name='Test field',
            attr_type=AttributeType.objects.get(name='text'),
            index=0
        )
        Attribute.objects.create(
            schema=schema,
            name='homeowner',
            long_name='Homeowner',
            attr_type=AttributeType.objects.get(name='boolean'),
            index=1
        )
        Attribute.objects.create(
            schema=schema,
            name='age',
            long_name='Homeowner Age',
            attr_type=AttributeType.objects.get(name='integer'),
            index=2, required=True, default=0
        )

        party = PartyFactory.create(
            project=project,
            attributes={'homeowner': True, 'fname': 'test', 'age': 35}
        )
        form = forms.PartyForm(project=project, instance=party, data=data)
        form.is_valid()
        form.save()

        assert Party.objects.filter(project=project).count() == 1
        party = Party.objects.filter(project=project).first()
        assert party.attributes.get('fname') == 'updated value'
        assert party.attributes.get('age') == 37

    def test_clean(self):
        data = {
            'name': 'Cadasta',
            'type': 'IN',
            'party::in::fname': 'test',
            'party::in::homeowner': True
        }
        project = ProjectFactory.create()
        questionnaire = q_factories.QuestionnaireFactory.create(
            project=project)

        content_type = ContentType.objects.get(
            app_label='party', model='party')
        schema = Schema.objects.create(
            content_type=content_type,
            selectors=(
                project.organization.id, project.id, questionnaire.id, ))
        Attribute.objects.create(
            schema=schema,
            name='fname',
            long_name='Test field',
            attr_type=AttributeType.objects.get(name='text'),
            index=0, required=False
        )
        schema_in = Schema.objects.create(
            content_type=content_type,
            selectors=(
                project.organization.id, project.id, questionnaire.id, 'IN'))
        Attribute.objects.create(
            schema=schema_in,
            name='homeowner',
            long_name='Homeowner',
            attr_type=AttributeType.objects.get(name='boolean'),
            index=1, required=True
        )
        schema_gr = Schema.objects.create(
            content_type=content_type,
            selectors=(
                project.organization.id, project.id, questionnaire.id, 'GR'))
        Attribute.objects.create(
            schema=schema_gr,
            name='group_name',
            long_name='Test field',
            attr_type=AttributeType.objects.get(name='text'),
            index=1, required=True
        )

        form = forms.PartyForm(project=project, data=data)
        assert form.is_valid()
        form.save()

        assert Party.objects.filter(project=project).count() == 1
        party = Party.objects.filter(project=project).first()
        assert party.attributes.get('fname') == 'test'
        assert party.attributes.get('homeowner')

    def test_field_sanitation(self):
        data = {
            'name': '<Cadasta>',
            'type': 'IN',
            'party::in::fname': '<FName>',
            'party::in::age': 37
        }
        project = ProjectFactory.create()
        content_type = ContentType.objects.get(
            app_label='party', model='party')
        schema = Schema.objects.create(
            content_type=content_type,
            selectors=(project.organization.id, project.id, ))

        Attribute.objects.create(
            schema=schema,
            name='fname',
            long_name='Test field',
            attr_type=AttributeType.objects.get(name='text'),
            index=0
        )
        Attribute.objects.create(
            schema=schema,
            name='homeowner',
            long_name='Homeowner',
            attr_type=AttributeType.objects.get(name='boolean'),
            index=1
        )
        Attribute.objects.create(
            schema=schema,
            name='age',
            long_name='Homeowner Age',
            attr_type=AttributeType.objects.get(name='integer'),
            index=2, required=True, default=0
        )

        form = forms.PartyForm(project=project, data=data)
        assert form.is_valid() is False
        assert form.errors.get('name') is not None
        assert form.errors.get('party::in::fname') is not None


class TenureRelationshipEditFormTest(UserTestCase, TestCase):

    def test_init(self):
        project = ProjectFactory.create()
        form = forms.TenureRelationshipEditForm(project=project)

        assert (list(form.fields['tenure_type'].choices) ==
                list(TENURE_RELATIONSHIP_TYPES))
        assert hasattr(form.fields['tenure_type'], 'labels_xlang') is False

    def test_init_with_form(self):
        project = ProjectFactory.create()
        questionnaire = q_factories.QuestionnaireFactory(project=project)
        q_factories.QuestionFactory.create(
            name='tenure_type',
            questionnaire=questionnaire,
            label={'en': 'Type', 'de': 'Typ'})
        form = forms.TenureRelationshipEditForm(project)
        assert hasattr(form.fields['tenure_type'], 'labels_xlang') is True

    def test_field_sanitation(self):
        data = {
            'tenure_type': 'FH',
            'tenurerelationship::default::fname': '<FName>',
            'tenurerelationship::default::age': 37
        }
        project = ProjectFactory.create()
        content_type = ContentType.objects.get(
            app_label='party', model='tenurerelationship')
        schema = Schema.objects.create(
            content_type=content_type,
            selectors=(project.organization.id, project.id, ))

        Attribute.objects.create(
            schema=schema,
            name='fname',
            long_name='Test field',
            attr_type=AttributeType.objects.get(name='text'),
            index=0
        )
        Attribute.objects.create(
            schema=schema,
            name='age',
            long_name='Homeowner Age',
            attr_type=AttributeType.objects.get(name='integer'),
            index=1, required=True, default=0
        )

        form = forms.TenureRelationshipEditForm(project=project, data=data)
        assert form.is_valid() is False
        assert (form.errors.get('tenurerelationship::default::fname')
                is not None)
