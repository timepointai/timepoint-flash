"""Tests for character interaction agents.

Tests each agent's:
    - Initialization
    - Input validation
    - Output formatting
    - Sentiment analysis
    - Session management
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.config import ProviderType
from app.agents import (
    CharacterChatAgent,
    ChatInput,
    ChatOutput,
    ChatSessionManager,
    get_session_manager,
    DialogExtensionAgent,
    DialogExtensionInput,
    SurveyAgent,
    SurveyInput,
)
from app.core.providers import LLMResponse
from app.schemas import Character, CharacterRole, DialogLine
from app.schemas.chat import (
    ChatSession,
    ChatMessage,
    ChatRole,
    SurveyMode,
    CharacterSurveyResponse,
    SurveyResult,
    DialogExtensionResponse,
)


# =============================================================================
# CharacterChatAgent Tests
# =============================================================================


@pytest.mark.fast
class TestCharacterChatAgent:
    """Tests for CharacterChatAgent."""

    def test_initialization(self):
        """Test CharacterChatAgent initialization."""
        agent = CharacterChatAgent()
        assert agent.name == "CharacterChatAgent"

    def test_initialization_with_custom_name(self):
        """Test CharacterChatAgent with custom name."""
        agent = CharacterChatAgent(name="CustomChat")
        assert agent.name == "CustomChat"

    def test_build_character_bio(self):
        """Test character biography generation."""
        agent = CharacterChatAgent()
        character = Character(
            name="Benjamin Franklin",
            role=CharacterRole.PRIMARY,
            description="Founding Father",
            personality="Witty and wise",
            speaking_style="Aphoristic",
        )

        bio = agent._build_character_bio(character)

        assert "PERSONALITY: Witty and wise" in bio
        assert "SPEAKING STYLE: Aphoristic" in bio
        assert "APPEARANCE: Founding Father" in bio

    def test_build_character_bio_minimal(self):
        """Test bio generation with minimal data."""
        agent = CharacterChatAgent()
        character = Character(
            name="Unknown",
            role=CharacterRole.BACKGROUND,
            description="A bystander",
        )

        bio = agent._build_character_bio(character)
        assert "APPEARANCE: A bystander" in bio

    def test_detect_emotional_tone_joyful(self):
        """Test emotional tone detection for joyful responses."""
        agent = CharacterChatAgent()

        text = "I am delighted by this wonderful news!"
        tone = agent._detect_emotional_tone(text)
        assert tone == "joyful"

    def test_detect_emotional_tone_anxious(self):
        """Test emotional tone detection for anxious responses."""
        agent = CharacterChatAgent()

        text = "I am filled with worry and fear about the future."
        tone = agent._detect_emotional_tone(text)
        assert tone == "anxious"

    def test_detect_emotional_tone_curious(self):
        """Test emotional tone detection for curious responses."""
        agent = CharacterChatAgent()

        text = "I wonder what fascinating things we might discover."
        tone = agent._detect_emotional_tone(text)
        assert tone == "curious"

    def test_detect_emotional_tone_default(self):
        """Test emotional tone detection returns neutral by default."""
        agent = CharacterChatAgent()

        text = "The situation requires consideration."
        tone = agent._detect_emotional_tone(text)
        assert tone == "neutral"

    @pytest.mark.asyncio
    async def test_chat_success(self):
        """Test successful chat interaction."""
        mock_router = MagicMock()
        mock_router.call = AsyncMock(
            return_value=LLMResponse(
                content="Indeed, liberty is the foundation of our endeavor.",
                model="test-model",
                provider=ProviderType.GOOGLE,
            )
        )

        agent = CharacterChatAgent(router=mock_router)
        character = Character(
            name="Thomas Jefferson",
            role=CharacterRole.PRIMARY,
            description="Author of Declaration",
        )

        input_data = ChatInput(
            character=character,
            message="What do you think of liberty?",
            year=1776,
            location="Philadelphia",
        )

        result = await agent.chat(input_data)

        assert result.success is True
        assert result.content is not None
        assert result.content.response == "Indeed, liberty is the foundation of our endeavor."
        assert result.content.character_name == "Thomas Jefferson"

    @pytest.mark.asyncio
    async def test_chat_with_history(self):
        """Test chat with conversation history."""
        mock_router = MagicMock()
        mock_router.call = AsyncMock(
            return_value=LLMResponse(
                content="As I mentioned before, education is paramount.",
                model="test-model",
                provider=ProviderType.GOOGLE,
            )
        )

        agent = CharacterChatAgent(router=mock_router)
        character = Character(
            name="Benjamin Franklin",
            role=CharacterRole.PRIMARY,
            description="Founding Father and inventor",
        )

        history = [
            ChatMessage(role=ChatRole.USER, content="Tell me about education."),
            ChatMessage(role=ChatRole.CHARACTER, content="Education is the foundation of wisdom."),
        ]

        input_data = ChatInput(
            character=character,
            message="Can you elaborate?",
            year=1776,
            location="Philadelphia",
            history=history,
        )

        result = await agent.chat(input_data)

        assert result.success is True
        # Verify the call was made
        mock_router.call.assert_called_once()

    @pytest.mark.asyncio
    async def test_chat_failure(self):
        """Test handling chat failure."""
        mock_router = MagicMock()
        mock_router.call = AsyncMock(side_effect=Exception("API error"))

        agent = CharacterChatAgent(router=mock_router)
        character = Character(
            name="John Adams",
            role=CharacterRole.PRIMARY,
            description="Patriot",
        )

        input_data = ChatInput(
            character=character,
            message="Hello",
            year=1776,
            location="Boston",
        )

        result = await agent.chat(input_data)

        assert result.success is False
        assert "API error" in result.error


@pytest.mark.fast
class TestChatInput:
    """Tests for ChatInput dataclass."""

    def test_chat_input_creation(self):
        """Test ChatInput creation."""
        character = Character(
            name="George Washington",
            role=CharacterRole.PRIMARY,
            description="General",
        )

        input_data = ChatInput(
            character=character,
            message="How are you?",
            year=1776,
            location="Valley Forge",
        )

        assert input_data.character.name == "George Washington"
        assert input_data.message == "How are you?"
        assert input_data.year == 1776

    def test_chat_input_optional_fields(self):
        """Test ChatInput with optional fields."""
        character = Character(
            name="Test Character",
            role=CharacterRole.SECONDARY,
            description="Test",
        )

        input_data = ChatInput(
            character=character,
            message="Test",
            year=1776,
            location="Test",
            era="Test Era",
            scene_context="A test scene",
        )

        assert input_data.era == "Test Era"
        assert input_data.scene_context == "A test scene"


@pytest.mark.fast
class TestChatSessionManager:
    """Tests for ChatSessionManager."""

    def test_initialization(self):
        """Test ChatSessionManager initialization."""
        manager = ChatSessionManager()
        assert manager.sessions == {}

    def test_create_session(self):
        """Test session creation."""
        manager = ChatSessionManager()

        session = manager.create_session(
            timepoint_id="tp-123",
            character_name="Benjamin Franklin",
        )

        assert session is not None
        assert session.timepoint_id == "tp-123"
        assert session.character_name == "Benjamin Franklin"
        assert len(session.messages) == 0

    def test_get_session(self):
        """Test retrieving existing session."""
        manager = ChatSessionManager()

        session = manager.create_session(
            timepoint_id="tp-123",
            character_name="Ben Franklin",
        )

        retrieved = manager.get_session(session.id)
        assert retrieved is not None
        assert retrieved.id == session.id

    def test_get_nonexistent_session(self):
        """Test retrieving nonexistent session."""
        manager = ChatSessionManager()

        result = manager.get_session("nonexistent-id")
        assert result is None

    def test_add_message(self):
        """Test adding message to session."""
        manager = ChatSessionManager()

        session = manager.create_session(
            timepoint_id="tp-123",
            character_name="Test",
        )

        result1 = manager.add_message(session.id, "user", "Hello")
        result2 = manager.add_message(session.id, "character", "Hi there")

        assert result1 is True
        assert result2 is True

        updated = manager.get_session(session.id)
        assert len(updated.messages) == 2
        assert updated.messages[0].role == ChatRole.USER
        assert updated.messages[1].role == ChatRole.CHARACTER

    def test_get_sessions_for_timepoint(self):
        """Test listing sessions for a timepoint."""
        manager = ChatSessionManager()

        manager.create_session("tp-123", "Character A")
        manager.create_session("tp-123", "Character B")
        manager.create_session("tp-456", "Character C")

        sessions = manager.get_sessions_for_timepoint("tp-123")
        assert len(sessions) == 2

    def test_delete_session(self):
        """Test deleting a session."""
        manager = ChatSessionManager()

        session = manager.create_session("tp-123", "Test")
        manager.delete_session(session.id)

        assert manager.get_session(session.id) is None

    def test_get_session_manager_singleton(self):
        """Test session manager singleton."""
        manager1 = get_session_manager()
        manager2 = get_session_manager()
        assert manager1 is manager2


# =============================================================================
# DialogExtensionAgent Tests
# =============================================================================


@pytest.mark.fast
class TestDialogExtensionAgent:
    """Tests for DialogExtensionAgent."""

    def test_initialization(self):
        """Test DialogExtensionAgent initialization."""
        agent = DialogExtensionAgent()
        assert agent.name == "DialogExtensionAgent"

    def test_initialization_with_custom_name(self):
        """Test DialogExtensionAgent with custom name."""
        agent = DialogExtensionAgent(name="CustomDialog")
        assert agent.name == "CustomDialog"

    def test_format_existing_dialog(self):
        """Test formatting existing dialog for prompt."""
        agent = DialogExtensionAgent()

        dialog = [
            DialogLine(speaker="John Adams", text="We must proceed.", tone="serious"),
            DialogLine(speaker="Ben Franklin", text="Indeed we must.", tone="calm"),
        ]

        formatted = agent._format_existing_dialog(dialog)

        assert "John Adams" in formatted
        assert "We must proceed." in formatted
        assert "Ben Franklin" in formatted

    def test_format_existing_dialog_empty(self):
        """Test formatting empty dialog."""
        agent = DialogExtensionAgent()

        formatted = agent._format_existing_dialog([])
        assert "(No previous dialog)" in formatted

    def test_filter_characters_no_filter(self):
        """Test filtering characters without specified names."""
        agent = DialogExtensionAgent()

        characters = [
            Character(name="John Adams", role=CharacterRole.PRIMARY, description="Patriot", speaks_in_scene=True),
            Character(name="Ben Franklin", role=CharacterRole.PRIMARY, description="Inventor", speaks_in_scene=True),
        ]

        filtered = agent._filter_characters(characters, None)

        assert len(filtered) == 2

    def test_filter_characters_with_names(self):
        """Test filtering characters by specific names."""
        agent = DialogExtensionAgent()

        characters = [
            Character(name="John Adams", role=CharacterRole.PRIMARY, description="Patriot"),
            Character(name="Ben Franklin", role=CharacterRole.PRIMARY, description="Inventor"),
            Character(name="Thomas Jefferson", role=CharacterRole.PRIMARY, description="Author"),
        ]

        filtered = agent._filter_characters(characters, ["John Adams", "Thomas Jefferson"])

        assert len(filtered) == 2
        names = [c.name for c in filtered]
        assert "Ben Franklin" not in names

    @pytest.mark.asyncio
    async def test_extend_success(self):
        """Test successful dialog extension."""
        mock_router = MagicMock()
        mock_router.call_structured = AsyncMock(
            return_value=LLMResponse(
                content=DialogExtensionResponse(
                    dialog=[
                        {"speaker": "John Adams", "text": "We must proceed."},
                        {"speaker": "Ben Franklin", "text": "Indeed we must."},
                    ],
                    context="Continued deliberation",
                    characters_involved=["John Adams", "Ben Franklin"],
                ),
                model="test-model",
                provider=ProviderType.GOOGLE,
            )
        )

        agent = DialogExtensionAgent(router=mock_router)

        characters = [
            Character(name="John Adams", role=CharacterRole.PRIMARY, description="Patriot", speaks_in_scene=True),
            Character(name="Ben Franklin", role=CharacterRole.PRIMARY, description="Inventor", speaks_in_scene=True),
        ]

        input_data = DialogExtensionInput(
            characters=characters,
            existing_dialog=[DialogLine(speaker="Adams", text="Let us begin.")],
            year=1776,
            location="Philadelphia",
            num_lines=2,
        )

        result = await agent.extend(input_data)

        assert result.success is True
        assert result.content is not None

    @pytest.mark.asyncio
    async def test_extend_no_characters(self):
        """Test extend with no characters available."""
        agent = DialogExtensionAgent()

        input_data = DialogExtensionInput(
            characters=[],
            existing_dialog=[],
            year=1776,
            location="Test",
        )

        result = await agent.extend(input_data)

        assert result.success is False
        assert "No characters" in result.error

    @pytest.mark.asyncio
    async def test_extend_failure(self):
        """Test handling extension failure."""
        mock_router = MagicMock()
        mock_router.call_structured = AsyncMock(side_effect=Exception("API error"))

        agent = DialogExtensionAgent(router=mock_router)

        input_data = DialogExtensionInput(
            characters=[Character(name="Test", role=CharacterRole.PRIMARY, description="Test", speaks_in_scene=True)],
            existing_dialog=[],
            year=1776,
            location="Test",
        )

        result = await agent.extend(input_data)

        assert result.success is False
        assert "API error" in result.error


@pytest.mark.fast
class TestDialogExtensionInput:
    """Tests for DialogExtensionInput dataclass."""

    def test_input_creation(self):
        """Test DialogExtensionInput creation."""
        input_data = DialogExtensionInput(
            characters=[Character(name="Test", role=CharacterRole.PRIMARY, description="Test")],
            existing_dialog=[DialogLine(speaker="Test", text="Hello")],
            year=1776,
            location="Philadelphia",
            num_lines=5,
        )

        assert len(input_data.characters) == 1
        assert input_data.num_lines == 5

    def test_input_defaults(self):
        """Test DialogExtensionInput defaults."""
        input_data = DialogExtensionInput(
            characters=[],
            existing_dialog=[],
            year=1776,
            location="Test",
        )

        assert input_data.num_lines == 5
        assert input_data.prompt is None
        assert input_data.era is None


# =============================================================================
# SurveyAgent Tests
# =============================================================================


@pytest.mark.fast
class TestSurveyAgent:
    """Tests for SurveyAgent."""

    def test_initialization(self):
        """Test SurveyAgent initialization."""
        agent = SurveyAgent()
        assert agent.name == "SurveyAgent"

    def test_initialization_with_custom_name(self):
        """Test SurveyAgent with custom name."""
        agent = SurveyAgent(name="CustomSurvey")
        assert agent.name == "CustomSurvey"

    def test_build_character_bio(self):
        """Test character bio generation."""
        agent = SurveyAgent()

        character = Character(
            name="Alexander Hamilton",
            role=CharacterRole.PRIMARY,
            description="Treasury Secretary",
            historical_note="First Treasury Secretary",
            personality="Ambitious and brilliant",
            speaking_style="Eloquent and verbose",
            emotional_state="Determined",
        )

        bio = agent._build_character_bio(character)

        assert "Treasury Secretary" in bio
        assert "Ambitious" in bio
        assert "Eloquent" in bio

    def test_build_character_bio_minimal(self):
        """Test bio generation with minimal character data."""
        agent = SurveyAgent()

        character = Character(
            name="Unknown Person",
            role=CharacterRole.BACKGROUND,
            description="A bystander",
        )

        bio = agent._build_character_bio(character)
        assert "historical moment" in bio.lower()

    def test_analyze_sentiment_positive(self):
        """Test sentiment analysis for positive text."""
        agent = SurveyAgent()

        text = "I strongly support this initiative and am pleased with the progress."
        sentiment = agent._analyze_sentiment(text)
        assert sentiment == "positive"

    def test_analyze_sentiment_negative(self):
        """Test sentiment analysis for negative text."""
        agent = SurveyAgent()

        text = "I am worried and have grave doubts about this approach."
        sentiment = agent._analyze_sentiment(text)
        assert sentiment == "negative"

    def test_analyze_sentiment_mixed(self):
        """Test sentiment analysis for mixed text."""
        agent = SurveyAgent()

        text = "I support this endeavor but am concerned about the risks."
        sentiment = agent._analyze_sentiment(text)
        assert sentiment == "mixed"

    def test_analyze_sentiment_neutral(self):
        """Test sentiment analysis for neutral text."""
        agent = SurveyAgent()

        text = "The matter requires further consideration and analysis."
        sentiment = agent._analyze_sentiment(text)
        assert sentiment == "neutral"

    def test_extract_key_points(self):
        """Test key point extraction."""
        agent = SurveyAgent()

        text = "First point. Second point. Third point. Fourth point. Fifth point."
        key_points = agent._extract_key_points(text)

        assert len(key_points) == 3  # Only first 3
        assert "First point" in key_points[0]

    def test_detect_emotional_tone_passionate(self):
        """Test emotional tone detection for passionate."""
        agent = SurveyAgent()

        text = "I am passionately devoted to this cause!"
        tone = agent._detect_emotional_tone(text)
        assert tone == "passionate"

    def test_detect_emotional_tone_angry(self):
        """Test emotional tone detection for angry."""
        agent = SurveyAgent()

        text = "This fills me with outrage and anger!"
        tone = agent._detect_emotional_tone(text)
        assert tone == "angry"

    @pytest.mark.asyncio
    async def test_survey_parallel(self):
        """Test parallel survey execution."""
        mock_router = MagicMock()
        mock_router.call = AsyncMock(
            return_value=LLMResponse(
                content="This is my thoughtful response on the matter.",
                model="test-model",
                provider=ProviderType.GOOGLE,
            )
        )

        agent = SurveyAgent(router=mock_router)

        characters = [
            Character(name="John Adams", role=CharacterRole.PRIMARY, description="Patriot"),
            Character(name="Benjamin Franklin", role=CharacterRole.PRIMARY, description="Inventor"),
        ]

        input_data = SurveyInput(
            characters=characters,
            questions=["What do you think of independence?"],
            year=1776,
            location="Philadelphia",
            mode=SurveyMode.PARALLEL,
            include_summary=False,
        )

        result = await agent.survey(input_data)

        assert result.success is True
        assert result.content is not None
        assert len(result.content.responses) == 2

    @pytest.mark.asyncio
    async def test_survey_sequential(self):
        """Test sequential survey execution."""
        mock_router = MagicMock()
        mock_router.call = AsyncMock(
            return_value=LLMResponse(
                content="My considered opinion on this matter.",
                model="test-model",
                provider=ProviderType.GOOGLE,
            )
        )

        agent = SurveyAgent(router=mock_router)

        characters = [
            Character(name="Character A", role=CharacterRole.PRIMARY, description="Test A"),
            Character(name="Character B", role=CharacterRole.PRIMARY, description="Test B"),
        ]

        input_data = SurveyInput(
            characters=characters,
            questions=["What is your view?"],
            year=1776,
            location="Test",
            mode=SurveyMode.SEQUENTIAL,
            chain_prompts=True,
            include_summary=False,
        )

        result = await agent.survey(input_data)

        assert result.success is True
        assert len(result.content.responses) == 2
        assert result.content.mode == SurveyMode.SEQUENTIAL

    @pytest.mark.asyncio
    async def test_survey_no_characters(self):
        """Test survey with no characters."""
        agent = SurveyAgent()

        input_data = SurveyInput(
            characters=[],
            questions=["Test question"],
            year=1776,
            location="Test",
        )

        result = await agent.survey(input_data)

        assert result.success is False
        assert "No characters" in result.error

    @pytest.mark.asyncio
    async def test_survey_no_questions(self):
        """Test survey with no questions."""
        agent = SurveyAgent()

        input_data = SurveyInput(
            characters=[Character(name="Test", role=CharacterRole.PRIMARY, description="Test")],
            questions=[],
            year=1776,
            location="Test",
        )

        result = await agent.survey(input_data)

        assert result.success is False
        assert "No questions" in result.error

    @pytest.mark.asyncio
    async def test_survey_with_summary(self):
        """Test survey with summary generation."""
        mock_router = MagicMock()
        mock_router.call = AsyncMock(
            return_value=LLMResponse(
                content="A thoughtful response.",
                model="test-model",
                provider=ProviderType.GOOGLE,
            )
        )

        agent = SurveyAgent(router=mock_router)

        characters = [
            Character(name="Test Character", role=CharacterRole.PRIMARY, description="Test"),
        ]

        input_data = SurveyInput(
            characters=characters,
            questions=["What do you think?"],
            year=1776,
            location="Test",
            include_summary=True,
        )

        result = await agent.survey(input_data)

        assert result.success is True
        # Summary should be generated
        assert result.content.summary is not None


@pytest.mark.fast
class TestSurveyInput:
    """Tests for SurveyInput dataclass."""

    def test_input_creation(self):
        """Test SurveyInput creation."""
        characters = [Character(name="Test", role=CharacterRole.PRIMARY, description="Test")]

        input_data = SurveyInput(
            characters=characters,
            questions=["Question 1", "Question 2"],
            year=1776,
            location="Philadelphia",
        )

        assert len(input_data.questions) == 2
        assert input_data.mode == SurveyMode.PARALLEL

    def test_input_defaults(self):
        """Test SurveyInput defaults."""
        input_data = SurveyInput(
            characters=[],
            questions=[],
            year=1776,
            location="Test",
        )

        assert input_data.mode == SurveyMode.PARALLEL
        assert input_data.chain_prompts is False
        assert input_data.include_summary is True

    def test_from_timepoint_data_with_character_data(self):
        """Test creating SurveyInput from CharacterData."""
        from app.schemas import CharacterData

        char_data = CharacterData(
            characters=[
                Character(name="John Adams", role=CharacterRole.PRIMARY, description="Patriot"),
                Character(name="Ben Franklin", role=CharacterRole.PRIMARY, description="Inventor"),
            ],
            focal_character="John Adams",
        )

        input_data = SurveyInput.from_timepoint_data(
            characters=char_data,
            questions=["Test?"],
            year=1776,
            location="Philadelphia",
        )

        assert len(input_data.characters) == 2

    def test_from_timepoint_data_with_selected_characters(self):
        """Test filtering characters by name."""
        from app.schemas import CharacterData

        char_data = CharacterData(
            characters=[
                Character(name="John Adams", role=CharacterRole.PRIMARY, description="Patriot"),
                Character(name="Ben Franklin", role=CharacterRole.PRIMARY, description="Inventor"),
                Character(name="Thomas Jefferson", role=CharacterRole.PRIMARY, description="Author"),
            ],
            focal_character="John Adams",
        )

        input_data = SurveyInput.from_timepoint_data(
            characters=char_data,
            questions=["Test?"],
            year=1776,
            location="Philadelphia",
            selected_characters=["John Adams", "Thomas Jefferson"],
        )

        assert len(input_data.characters) == 2
        names = [c.name for c in input_data.characters]
        assert "Ben Franklin" not in names
