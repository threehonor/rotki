import logging
from typing import TYPE_CHECKING, Any

from rotkehlchen.assets.utils import get_or_create_evm_token
from rotkehlchen.chain.ethereum.utils import token_normalized_value
from rotkehlchen.chain.evm.decoding.interfaces import DecoderInterface
from rotkehlchen.chain.evm.decoding.structures import (
    DEFAULT_DECODING_OUTPUT,
    DecoderContext,
    DecodingOutput,
)
from rotkehlchen.chain.evm.decoding.types import CounterpartyDetails
from rotkehlchen.history.events.structures.evm_event import EvmProduct
from rotkehlchen.history.events.structures.types import HistoryEventSubType, HistoryEventType
from rotkehlchen.logging import RotkehlchenLogsAdapter
from rotkehlchen.types import ChainID, ChecksumEvmAddress, Timestamp
from rotkehlchen.utils.misc import hex_or_bytes_to_address, hex_or_bytes_to_int, timestamp_to_date

from .constants import CLAIMED, CPT_PALADIN, PALADIN_MERKLE_DISTRIBUTOR_V2

if TYPE_CHECKING:
    from rotkehlchen.chain.ethereum.node_inquirer import EthereumInquirer
    from rotkehlchen.chain.evm.decoding.base import BaseDecoderTools
    from rotkehlchen.user_messages import MessagesAggregator


logger = logging.getLogger(__name__)
log = RotkehlchenLogsAdapter(logger)


class PaladinDecoder(DecoderInterface):

    def __init__(
            self,
            ethereum_inquirer: 'EthereumInquirer',
            base_tools: 'BaseDecoderTools',
            msg_aggregator: 'MessagesAggregator',
    ) -> None:
        super().__init__(
            evm_inquirer=ethereum_inquirer,
            base_tools=base_tools,
            msg_aggregator=msg_aggregator,
        )

    def _decode_claim_quest(self, context: DecoderContext) -> DecodingOutput:
        if context.tx_log.topics[0] != CLAIMED:
            return DEFAULT_DECODING_OUTPUT

        if not self.base.is_tracked(user_address := hex_or_bytes_to_address(context.tx_log.topics[3])):  # noqa: E501
            return DEFAULT_DECODING_OUTPUT

        amount = hex_or_bytes_to_int(context.tx_log.data[32:64])
        reward_token_address = hex_or_bytes_to_address(context.tx_log.data[64:96])
        period = Timestamp(hex_or_bytes_to_int(context.tx_log.topics[2]))
        claimed_token = get_or_create_evm_token(
            userdb=self.base.database,
            evm_address=reward_token_address,
            chain_id=ChainID.ETHEREUM,
            evm_inquirer=self.evm_inquirer,
        )
        normalized_amount = token_normalized_value(amount, claimed_token)
        for event in context.decoded_events:
            if event.event_type == HistoryEventType.RECEIVE and event.event_subtype == HistoryEventSubType.NONE and event.asset == claimed_token and event.balance.amount == normalized_amount and event.location_label == user_address:  # noqa: E501
                event.event_subtype = HistoryEventSubType.REWARD
                event.counterparty = CPT_PALADIN
                event.notes = f'Claim {normalized_amount} {claimed_token.symbol} from Paladin veCRV bribes for the period starting at {timestamp_to_date(period, formatstr="%d/%m/%Y %H:%M:%S")}'  # noqa: E501
                event.product = EvmProduct.BRIBE
                break
        else:  # not found
            log.error(f'Paladin bribe transfer was not found for {context.transaction.tx_hash.hex()}')  # noqa: E501
        return DEFAULT_DECODING_OUTPUT

    # -- DecoderInterface methods

    def addresses_to_decoders(self) -> dict[ChecksumEvmAddress, tuple[Any, ...]]:
        return {
            PALADIN_MERKLE_DISTRIBUTOR_V2: (self._decode_claim_quest,),
        }

    @staticmethod
    def counterparties() -> tuple[CounterpartyDetails, ...]:
        return (CounterpartyDetails(
            identifier=CPT_PALADIN,
            label='Paladin',
            image='paladin.png',
        ),)
