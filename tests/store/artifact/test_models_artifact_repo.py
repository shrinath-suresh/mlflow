import pytest
from unittest import mock
from unittest.mock import Mock

from mlflow.entities.model_registry import ModelVersion
from mlflow.exceptions import MlflowException
from mlflow.store.artifact.dbfs_artifact_repo import DbfsRestArtifactRepository
from mlflow.store.artifact.models_artifact_repo import ModelsArtifactRepository
from mlflow.tracking import MlflowClient

# pylint: disable=unused-import
from tests.store.artifact.test_dbfs_artifact_repo_delegation import host_creds_mock


@pytest.fixture
def mock_get_model_version_download_uri(artifact_location):
    with mock.patch.object(
        MlflowClient, "get_model_version_download_uri", return_value=artifact_location
    ) as mockval:
        yield mockval.return_value


@pytest.mark.parametrize(
    "uri, expected_name, expected_version",
    [
        ("models:/AdsModel1/0", "AdsModel1", 0),
        ("models:/Ads Model 1/12345", "Ads Model 1", 12345),
        ("models:/12345/67890", "12345", 67890),
        ("models://profile@databricks/12345/67890", "12345", 67890),
    ],
)
def test_parse_models_uri_with_version(uri, expected_name, expected_version):
    (name, version, stage) = ModelsArtifactRepository._parse_uri(uri)
    assert name == expected_name
    assert version == expected_version
    assert stage is None


@pytest.mark.parametrize(
    "uri, expected_name, expected_stage",
    [
        ("models:/AdsModel1/Production", "AdsModel1", "Production"),
        ("models:/Ads Model 1/None", "Ads Model 1", "None"),
        ("models://scope:key@databricks/Ads Model 1/None", "Ads Model 1", "None"),
    ],
)
def test_parse_models_uri_with_stage(uri, expected_name, expected_stage):
    (name, version, stage) = ModelsArtifactRepository._parse_uri(uri)
    assert name == expected_name
    assert version is None
    assert stage == expected_stage


@pytest.mark.parametrize(
    "uri",
    [
        "notmodels:/NameOfModel/12345",  # wrong scheme with version
        "notmodels:/NameOfModel/StageName",  # wrong scheme with stage
        "models:/",  # no model name
        "models:/Name/Stage/0",  # too many specifiers
        "models:Name/Stage",  # missing slash
        "models://Name/Stage",  # hostnames are ignored, path too short
    ],
)
def test_parse_models_uri_invalid_input(uri):
    with pytest.raises(MlflowException):
        ModelsArtifactRepository._parse_uri(uri)


@pytest.mark.parametrize(
    "artifact_location", ["dbfs:/databricks/mlflow-registry/12345/models/keras-model"]
)
def test_models_artifact_repo_init_with_version_uri(
    host_creds_mock, mock_get_model_version_download_uri, artifact_location
):  # pylint: disable=unused-argument
    model_uri = "models:/MyModel/12"
    models_repo = ModelsArtifactRepository(model_uri)
    assert models_repo.artifact_uri == model_uri
    assert isinstance(models_repo.repo, DbfsRestArtifactRepository)
    assert models_repo.repo.artifact_uri == artifact_location

    # Also confirm that since no databricks:// registry|tracking URI is set in the environment,
    # databricks profile information not is added to the final DBFS URI.
    with mock.patch(
        "mlflow.store.artifact.dbfs_artifact_repo.DbfsRestArtifactRepository", autospec=True
    ) as mock_repo:
        models_repo = ModelsArtifactRepository(model_uri)
        assert models_repo.artifact_uri == model_uri
        assert isinstance(models_repo.repo, DbfsRestArtifactRepository)
        mock_repo.assert_called_once_with(
            "dbfs:/databricks/mlflow-registry/12345/models/keras-model"
        )


@pytest.mark.parametrize(
    "artifact_location", ["dbfs:/databricks/mlflow-registry/12345/models/keras-model"]
)
def test_models_artifact_repo_init_with_version_uri_and_db_profile(
    mock_get_model_version_download_uri,
):  # pylint: disable=unused-argument
    model_uri = "models://profile@databricks/MyModel/12"
    final_uri = "dbfs://profile@databricks/databricks/mlflow-registry/12345/models/keras-model"
    with mock.patch(
        "mlflow.store.artifact.dbfs_artifact_repo.DbfsRestArtifactRepository", autospec=True
    ) as mock_repo:
        models_repo = ModelsArtifactRepository(model_uri)
        assert models_repo.artifact_uri == model_uri
        assert isinstance(models_repo.repo, DbfsRestArtifactRepository)
        mock_repo.assert_called_once_with(final_uri)


@pytest.mark.parametrize(
    "artifact_location", ["dbfs:/databricks/mlflow-registry/12345/models/keras-model"]
)
def test_models_artifact_repo_init_with_version_uri_and_db_profile_from_context(
    mock_get_model_version_download_uri,
):  # pylint: disable=unused-argument
    model_uri = "models:/MyModel/12"
    with mock.patch(
        "mlflow.store.artifact.dbfs_artifact_repo.DbfsRestArtifactRepository", autospec=True
    ) as mock_repo, mock.patch("mlflow.get_registry_uri", return_value="databricks://scope:key"):
        models_repo = ModelsArtifactRepository(model_uri)
        assert models_repo.artifact_uri == model_uri
        assert isinstance(models_repo.repo, DbfsRestArtifactRepository)
        mock_repo.assert_called_once_with(
            "dbfs://scope:key@databricks/databricks/mlflow-registry/12345/models/keras-model"
        )


@pytest.mark.parametrize(
    "artifact_location", ["dbfs:/databricks/mlflow-registry/12345/models/keras-model"]
)
def test_models_artifact_repo_init_with_version_uri_and_bad_db_profile_from_context(
    mock_get_model_version_download_uri,
):  # pylint: disable=unused-argument
    model_uri = "models:/MyModel/12"
    with mock.patch("mlflow.get_registry_uri", return_value="databricks://scope:key:invalid"):
        with pytest.raises(MlflowException) as ex:
            ModelsArtifactRepository(model_uri)
        assert "Key prefixes cannot contain" in ex.value.message


@pytest.mark.parametrize(
    "artifact_location", ["dbfs:/databricks/mlflow-registry/12345/models/keras-model"]
)
def test_models_artifact_repo_init_with_stage_uri(
    host_creds_mock, mock_get_model_version_download_uri, artifact_location
):  # pylint: disable=unused-argument
    model_uri = "models:/MyModel/Production"
    model_version_detailed = ModelVersion(
        "MyModel",
        "10",
        "2345671890",
        "234567890",
        "some description",
        "UserID",
        "Production",
        "source",
        "run12345",
    )
    get_latest_versions_patch = mock.patch.object(
        MlflowClient, "get_latest_versions", return_value=[model_version_detailed]
    )
    with get_latest_versions_patch:
        models_repo = ModelsArtifactRepository(model_uri)
        assert models_repo.artifact_uri == model_uri
        assert isinstance(models_repo.repo, DbfsRestArtifactRepository)
        assert models_repo.repo.artifact_uri == artifact_location


@pytest.mark.parametrize(
    "artifact_location", ["dbfs:/databricks/mlflow-registry/12345/models/keras-model"]
)
def test_models_artifact_repo_init_with_stage_uri_and_db_profile(
    mock_get_model_version_download_uri,
):  # pylint: disable=unused-argument
    model_uri = "models://profile@databricks/MyModel/Staging"
    final_uri = "dbfs://profile@databricks/databricks/mlflow-registry/12345/models/keras-model"
    model_version_detailed = ModelVersion(
        "MyModel",
        "10",
        "2345671890",
        "234567890",
        "some description",
        "UserID",
        "Production",
        "source",
        "run12345",
    )
    get_latest_versions_patch = mock.patch.object(
        MlflowClient, "get_latest_versions", return_value=[model_version_detailed]
    )
    with get_latest_versions_patch, mock.patch(
        "mlflow.store.artifact.dbfs_artifact_repo.DbfsRestArtifactRepository", autospec=True
    ) as mock_repo:
        models_repo = ModelsArtifactRepository(model_uri)
        assert models_repo.artifact_uri == model_uri
        assert isinstance(models_repo.repo, DbfsRestArtifactRepository)
        mock_repo.assert_called_once_with(final_uri)


@pytest.mark.parametrize("artifact_location", ["s3://blah_bucket/"])
def test_models_artifact_repo_uses_repo_download_artifacts(
    mock_get_model_version_download_uri,
):  # pylint: disable=unused-argument
    """
    ``ModelsArtifactRepository`` should delegate `download_artifacts` to its
    ``self.repo.download_artifacts`` function.
    """
    model_uri = "models:/MyModel/12"
    models_repo = ModelsArtifactRepository(model_uri)
    models_repo.repo = Mock()
    models_repo.download_artifacts("artifact_path", "dst_path")
    models_repo.repo.download_artifacts.assert_called_once()
