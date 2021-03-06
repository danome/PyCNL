# -*- Mode:python; c-file-style:"gnu"; indent-tabs-mode:nil -*- */
#
# Copyright (C) 2018-2019 Regents of the University of California.
# Author: Jeff Thompson <jefft0@remap.ucla.edu>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
# A copy of the GNU Lesser General Public License is in the file COPYING.

"""
This module defines the GeneralizedObjectStreamHandler class which extends
Namespace::Handler and attaches to a Namespace node to fetch the _latest packet
and use the name in it to start fetching the stream of generalized object using
a GeneralizedObjectHandler. However, if the pipelineSize is zero, continually
fetch the _latest packet and use its name to fetch the generalized object.
"""

import logging
from pyndn import Name, MetaInfo, DelegationSet
from pyndn.util.common import Common
from pycnl.namespace import Namespace, NamespaceState
from pycnl.generalized_object.generalized_object_handler import GeneralizedObjectHandler

class GeneralizedObjectStreamHandler(Namespace.Handler):
    """
    Create a GeneralizedObjectHandler with the optional
    onSequencedGeneralizedObject callback.

    :param Namespace namespace: (optional) Set the Namespace that this handler
      is attached to. If omitted or None, you can call setNamespace() later.
    :param int pipelineSize: (optional) The pipeline size (number of objects,
      not interests). The pipelineSize times the expected period between objects
      should be less than the maximum interest lifetime.
      However, if pipelineSize is zero, continually fetch the _latest packet and
      use its name to fetch the generalized object. In this case, the producer
      can call setLatestPacketFreshnessPeriod to set the freshness period to
      less than the expected period of producing new generalized objects.
      If omitted, use a pipeline size of 8.
    :param onSequencedGeneralizedObject: (optional) When the ContentMetaInfo is
      received for a new sequence number and the hasSegments is False, this calls
      onSequencedGeneralizedObject(sequenceNumber, contentMetaInfo, objectNamespace)
      where sequenceNumber is the new sequence number, contentMetaInfo is the
      ContentMetaInfo and objectNamespace.obj is the "other" info as a Blob or
      possibly deserialized into another type. If the hasSegments flag is True,
      when the segments are received and assembled into a single block of
      memory, this calls
      onSequencedGeneralizedObject(sequenceNumber, contentMetaInfo, objectNamespace)
      where sequenceNumber is the new sequence number, contentMetaInfo is the
      ContentMetaInfo and objectNamespace.obj is the object that was assembled
      from the segment contents as a Blob or possibly deserialized to another
      type. If you don't supply an onSequencedGeneralizedObject callback here,
      you can call addOnStateChanged on the Namespace object to which this is
      attached and listen for the OBJECT_READY state.
    :type onSequencedGeneralizedObject: function object
    """
    def __init__(self, namespace = None, pipelineSize = 8,
          onSequencedGeneralizedObject = None):
        super(GeneralizedObjectStreamHandler, self).__init__()

        if pipelineSize < 0:
            pipelineSize = 0
        self._pipelineSize = pipelineSize
        self._onSequencedGeneralizedObject = onSequencedGeneralizedObject
        self._latestNamespace = None
        self._producedSequenceNumber = -1
        self._latestPacketFreshnessPeriod = 1000.0
        self._generalizedObjectHandler = GeneralizedObjectHandler()
        self._nRequestedSequenceNumbers = 0
        self._maxRequestedSequenceNumber = -1
        self._nReportedSequenceNumbers = 0
        self._maxReportedSequenceNumber = -1

        if namespace != None:
            self.setNamespace(namespace)

    def setObject(self, sequenceNumber, obj, contentType, other = None):
        """
        Prepare the generalized object as a child of the given sequence number
        Namespace node under the getNamespace() node, according to
        GeneralizedObjectHandler.setObject. Also prepare to answer requests for
        the _latest packet which refer to the given sequence number Name.

        :param int sequenceNumber: The sequence number to publish. This updates
          the value for getProducedSequenceNumber()
        :param obj: The object to publish as a Generalized Object.
        :type obj: Blob or other type as determined by an attached handler
        :param str contentType: The content type for the content _meta packet.
        :param Blob other: (optional) If the "other" Blob size is greater than
          zero, then put it in the _meta packet and use segments for the object
          Blob (even if it is small). If the "other" Blob isNull() or the size
          is zero, then don't use it.
        """
        if self.namespace == None:
            raise RuntimeError(
              "GeneralizedObjectStreamHandler.setObject: The Namespace is not set")

        self._producedSequenceNumber = sequenceNumber
        sequenceNamespace = self.namespace[
          Name.Component.fromSequenceNumber(self._producedSequenceNumber)]
        self._generalizedObjectHandler.setObject(
          sequenceNamespace, obj, contentType, other)

    def addObject(self, obj, contentType, other = None):
        """
        Publish an object for the next sequence number by calling setObject
        where the sequenceNumber is the current getProducedSequenceNumber() + 1.

        :param obj: The object to publish as a Generalized Object.
        :type obj: Blob or other type as determined by an attached handler
        :param str contentType: The content type for the content _meta packet.
        :param Blob other: (optional) If the "other" Blob size is greater than
          zero, then put it in the _meta packet and use segments for the object
          Blob (even if it is small). If the "other" Blob isNull() or the size
          is zero, then don't use it.
        """
        self.setObject(self.getProducedSequenceNumber() + 1, obj, contentType, other)

    def getProducedSequenceNumber(self):
        """
        Get the latest produced sequence number.

        :return: The latest produced sequence number, or -1 if none have been
          produced.
        :rtype: int
        """
        return self._producedSequenceNumber

    def getLatestPacketFreshnessPeriod(self):
        """
        Get the freshness period to use for the produced _latest data packet.

        :return: The freshness period in milliseconds.
        :rtype: float
        """
        return self._latestPacketFreshnessPeriod

    def setLatestPacketFreshnessPeriod(self, latestPacketFreshnessPeriod):
        """
        Set the freshness period to use for the produced _latest data packet.

        :param float latestPacketFreshnessPeriod: The freshness period in
          milliseconds.
        """
        self._latestPacketFreshnessPeriod = Common.nonNegativeFloatOrNone(
          latestPacketFreshnessPeriod)

    def getPipelineSize(self):
        """
        Get the pipeline size.

        :return: The pipeline size.
        :rtype: int
        """
        return self._pipelineSize

    def setPipelineSize(self, pipelineSize):
        """
        Change the pipeline size that was set in the constructor. This is only
        valid if the pipeline size in the constructor was non-zero. It is an
        error to set the pipeline size to zero if it was non-zero and vice
        versa, since this behavior is undefined.

        :param int pipelineSize: The pipeline size.
        """
        if pipelineSize < 0:
            pipelineSize = 0

        if pipelineSize == 0 and self._pipelineSize > 0:
            raise RuntimeError(
              "GeneralizedObjectStreamHandler.setPipelineSize: Cannot change the pipeline size from non-zero to zero")
        if pipelineSize > 0 and self._pipelineSize == 0:
            raise RuntimeError(
              "GeneralizedObjectStreamHandler.setPipelineSize: Cannot change the pipeline size from zero to non-zero")

        self._pipelineSize = pipelineSize

    def getMaxSegmentPayloadLength(self):
        """
        Get the maximum length of the payload of one segment, used to split a
        larger payload into segments (if the ContentMetaInfo hasSegments is
        True for a particular generalized object).

        :return: The maximum payload length.
        :rtype: int
        """
        # Pass through to the GeneralizedObjectHandler.
        return self._generalizedObjectHandler.getMaxSegmentPayloadLength()

    def setMaxSegmentPayloadLength(self, maxSegmentPayloadLength):
        """
        Set the maximum length of the payload of one segment, used to split a
        larger payload into segments (if the ContentMetaInfo hasSegments is
        True for a particular generalized object).

        :param int maxSegmentPayloadLength: The maximum payload length.
        """
        # Pass through to the GeneralizedObjectHandler.
        self._generalizedObjectHandler.setMaxSegmentPayloadLength(maxSegmentPayloadLength)

    def _onNamespaceSet(self):
        self._latestNamespace = self.namespace[self.NAME_COMPONENT_LATEST]

        self.namespace.addOnObjectNeeded(self._onObjectNeeded)
        self.namespace.addOnStateChanged(self._onStateChanged)

    def _onObjectNeeded(self, namespace, neededNamespace, callbackId):
        """
        This is called for object needed at the Handler's namespace. If
        neededNamespace is the Handler's Namespace (called by the appliction),
        then fetch the _latest packet. If neededNamespace is for the _latest
        packet (from an incoming Interest), produce the _latest packet for the
        current sequence number.
        """
        if neededNamespace == self.namespace:
            # Assume this is called by a consumer. Fetch the _latest packet.
            self._latestNamespace.objectNeeded(True)
            return True

        if (neededNamespace == self._latestNamespace and
              self._producedSequenceNumber >= 0):
            # Produce the _latest Data packet.
            sequenceName = Name(self.namespace.name).append(
              Name.Component.fromSequenceNumber(self._producedSequenceNumber))
            delegations = DelegationSet()
            delegations.add(1, sequenceName)

            versionedLatest = self._latestNamespace[Name.Component.fromVersion
              (Common.getNowMilliseconds())]
            metaInfo = MetaInfo()
            metaInfo.setFreshnessPeriod(self._latestPacketFreshnessPeriod)
            versionedLatest.setNewDataMetaInfo(metaInfo)
            # Make the Data packet and reply to outstanding Interests.
            versionedLatest.serializeObject(delegations.wireEncode())

            return True

        return False

    def _onStateChanged(self, namespace, changedNamespace, state, callbackId):
        """
        This is called when a packet arrives. Parse the _latest packet and start
        fetching the stream of GeneralizedObject by sequence number.
        """
        if (state == NamespaceState.INTEREST_TIMEOUT or
             state == NamespaceState.INTEREST_NETWORK_NACK):
            logging.getLogger(__name__).info(
              "GeneralizedObjectStreamHandler: Got timeout or nack for " +
              changedNamespace.name.toUri())
            if changedNamespace == self._latestNamespace:
                # Timeout or network NACK, so try to fetch again.
                self._latestNamespace._getFace().callLater(
                  self._latestPacketFreshnessPeriod,
                  lambda: self._latestNamespace.objectNeeded(True));
                return
            elif (self._pipelineSize > 0 and
                  changedNamespace.name.size() == self.namespace.name.size() + 2 and
                  changedNamespace.name[-1].equals(
                    GeneralizedObjectHandler.NAME_COMPONENT_META) and
                  changedNamespace.name[-2].isSequenceNumber() and
                  changedNamespace.name[-2].toSequenceNumber() ==
                    self._maxRequestedSequenceNumber):
                # The highest pipelined request timed out, so request the _latest.
                # TODO: Should we do this for the lowest requested?
                logging.getLogger(__name__).info(
                  "GeneralizedObjectStreamHandler: Requesting _latest because the highest pipelined request timed out: " +
                  changedNamespace.name.toUri())
                self._latestNamespace.objectNeeded(True)
                return

        if (not (state == NamespaceState.OBJECT_READY and
                 changedNamespace.name.size() ==
                   self._latestNamespace.name.size() + 1 and
                 self._latestNamespace.name.isPrefixOf(changedNamespace.name) and
                 changedNamespace.name[-1].isVersion())):
            # Not a versioned _latest, so ignore.
            return

        # Decode the _latest packet to get the target to fetch.
        # TODO: Should this already have been done by deserialize()?)
        delegations = DelegationSet()
        delegations.wireDecode(changedNamespace.obj)
        if delegations.size() <= 0:
            return
        targetName = delegations.get(0).getName()
        if (not (self.namespace.name.isPrefixOf(targetName) and
                 targetName.size() == self.namespace.name.size() + 1 and
                 targetName[-1].isSequenceNumber())):
            # TODO: Report an error for invalid target name?
            return
        targetNamespace = self.namespace[targetName]

        # We may already have the target if this was triggered by the producer.
        if targetNamespace.obj == None:
            sequenceNumber = targetName[-1].toSequenceNumber()

            if self._pipelineSize == 0:
                # Fetch one generalized object.
                sequenceMeta = targetNamespace[
                  GeneralizedObjectHandler.NAME_COMPONENT_META]
                # Make sure we didn't already request it.
                if sequenceMeta.state < NamespaceState.INTEREST_EXPRESSED:
                    GeneralizedObjectHandler(targetNamespace,
                      self._makeOnGeneralizedObject(sequenceNumber))
                    sequenceMeta.objectNeeded()
            else:
                # Fetch by continuously filling the Interest pipeline.
                self._maxReportedSequenceNumber = sequenceNumber - 1
                # Reset the pipeline in case we are resuming after a timeout.
                self._nRequestedSequenceNumbers = self._nReportedSequenceNumbers
                self._requestNewSequenceNumbers()

        if self._pipelineSize == 0:
            # Schedule to fetch the next _latest packet.
            freshnessPeriod = changedNamespace.getData().getMetaInfo().getFreshnessPeriod()
            if freshnessPeriod == None or freshnessPeriod < 0:
                # No freshness period. We don't expect this.
                return
            self._latestNamespace._getFace().callLater(
              freshnessPeriod / 2, lambda: self._latestNamespace.objectNeeded(True));

    def _requestNewSequenceNumbers(self):
        """
        Request new child sequence numbers, up to the pipelineSize_.
        """
        nOutstandingSequenceNumbers = (self._nRequestedSequenceNumbers -
          self._nReportedSequenceNumbers)

        # Now find unrequested sequence numbers and request.
        sequenceNumber = self._maxReportedSequenceNumber
        while nOutstandingSequenceNumbers < self._pipelineSize:
            sequenceNumber += 1
            sequenceNamespace = self.namespace[
              Name.Component.fromSequenceNumber(sequenceNumber)]
            sequenceMeta = sequenceNamespace[
              GeneralizedObjectHandler.NAME_COMPONENT_META]
            if (sequenceMeta.data or
                sequenceMeta.state >= NamespaceState.INTEREST_EXPRESSED):
                # Already got the data packet or already requested.
                continue

            nOutstandingSequenceNumbers += 1
            self._nRequestedSequenceNumbers += 1

            GeneralizedObjectHandler(sequenceNamespace,
              self._makeOnGeneralizedObject(sequenceNumber))
            if sequenceNumber > self._maxRequestedSequenceNumber:
                self._maxRequestedSequenceNumber = sequenceNumber
            sequenceMeta.objectNeeded()

    def _makeOnGeneralizedObject(self, sequenceNumber):
        def onGeneralizedObject(contentMetaInfo, objectNamespace):
            if self._onSequencedGeneralizedObject != None:
                try:
                    self._onSequencedGeneralizedObject(
                      sequenceNumber, contentMetaInfo, objectNamespace)
                except:
                    logging.exception("Error in onSequencedGeneralizedObject")

            self._nReportedSequenceNumbers += 1
            if sequenceNumber > self._maxReportedSequenceNumber:
                self._maxReportedSequenceNumber = sequenceNumber

            if self._pipelineSize > 0:
                # Continue to fetch by filling the pipeline.
                self._requestNewSequenceNumbers()

        return onGeneralizedObject

    NAME_COMPONENT_LATEST = Name.Component("_latest")

    producedSequenceNumber = property(getProducedSequenceNumber)
    latestPacketFreshnessPeriod = property(getLatestPacketFreshnessPeriod, setLatestPacketFreshnessPeriod)
