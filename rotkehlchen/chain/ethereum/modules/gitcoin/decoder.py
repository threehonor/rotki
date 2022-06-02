import logging
from typing import TYPE_CHECKING, Callable, List

from rotkehlchen.accounting.structures.base import (
    HistoryBaseEntry,
    HistoryEventSubType,
    HistoryEventType,
)
from rotkehlchen.assets.asset import EthereumToken
from rotkehlchen.chain.ethereum.decoding.interfaces import DecoderInterface
from rotkehlchen.chain.ethereum.decoding.structures import ActionItem
from rotkehlchen.chain.ethereum.structures import EthereumTxReceiptLog
from rotkehlchen.chain.ethereum.types import string_to_ethereum_address
from rotkehlchen.logging import RotkehlchenLogsAdapter
from rotkehlchen.types import EthereumTransaction

from .constants import CPT_GITCOIN

if TYPE_CHECKING:
    from rotkehlchen.chain.ethereum.decoding.base import BaseDecoderTools
    from rotkehlchen.chain.ethereum.manager import EthereumManager
    from rotkehlchen.user_messages import MessagesAggregator


logger = logging.getLogger(__name__)
log = RotkehlchenLogsAdapter(logger)


GITCOIN_BULK_CHECKOUT = string_to_ethereum_address('0x7d655c57f71464B6f83811C55D84009Cd9f5221C')


class GitcoinDecoder(DecoderInterface):  # lgtm[py/missing-call-to-init]
    def __init__(  # pylint: disable=super-init-not-called
            self,
            ethereum_manager: 'EthereumManager',  # pylint: disable=unused-argument
            base_tools: 'BaseDecoderTools',
            msg_aggregator: 'MessagesAggregator',  # pylint: disable=unused-argument
    ) -> None:
        self.base = base_tools

    def _maybe_enrich_gitcoin_transfers(  # pylint: disable=no-self-use
            self,
            token: EthereumToken,  # pylint: disable=unused-argument
            tx_log: EthereumTxReceiptLog,  # pylint: disable=unused-argument
            transaction: EthereumTransaction,
            event: HistoryBaseEntry,
            action_items: List[ActionItem],  # pylint: disable=unused-argument
    ) -> bool:
        if transaction.to_address not in (
                '0xdf869FAD6dB91f437B59F1EdEFab319493D4C4cE',
                '0x7d655c57f71464B6f83811C55D84009Cd9f5221C',
        ):
            return False

        if event.event_type == HistoryEventType.SPEND:
            to_address = event.counterparty
            event.notes = f'Donate {event.balance.amount} {event.asset.symbol} to {to_address} via gitcoin'  # noqa: E501
        else:  # can only be RECEIVE
            from_address = event.counterparty
            event.notes = f'Receive donation of {event.balance.amount} {event.asset.symbol} from {from_address} via gitcoin'  # noqa: E501

        event.event_subtype = HistoryEventSubType.DONATE
        event.counterparty = CPT_GITCOIN
        return True

    # -- DecoderInterface methods

    def enricher_rules(self) -> List[Callable]:
        return [
            self._maybe_enrich_gitcoin_transfers,
        ]

    def counterparties(self) -> List[str]:
        return [CPT_GITCOIN]