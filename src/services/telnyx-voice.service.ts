/**
 * Telnyx Carrier Voice & TeXML Bridge Service
 * Blueprint V1.0.0 Section 1 (Mode C) & Section 5 Specification
 */

export class TelnyxVoiceService {
  /**
   * Generates initial TeXML Inbound response with Speech-to-Text Gather
   */
  static generateInboundTeXML(
    greetingText: string = 'Thank you for calling Apex Dental Studio. This is Emily, your AI patient coordinator. How can I help you today?',
    actionUrl: string = '/api/v1/voice/telnyx/respond'
  ): string {
    return `<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Gather input="speech" action="${actionUrl}" method="POST" timeout="5" speechTimeout="auto">
    <Say voice="Polly.Joanna-Neural" language="en-US">
      ${greetingText}
    </Say>
  </Gather>
  <Say voice="Polly.Joanna-Neural" language="en-US">
    I did not hear a response. Please hold or call back during our normal practice hours. Goodbye.
  </Say>
  <Hangup/>
</Response>`;
  }

  /**
   * Generates TeXML warm transfer bridge with Front-Desk Coordinator dial
   */
  static generateWarmTransferTeXML(
    operatorPhone: string = process.env.FRONT_DESK_TRANSFER_PHONE || '+15559876543',
    whisperNotice: string = 'Connecting you directly to our front desk coordinator right now. Please hold.'
  ): string {
    return `<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="Polly.Joanna-Neural" language="en-US">
    ${whisperNotice}
  </Say>
  <Dial timeout="25">${operatorPhone}</Dial>
</Response>`;
  }

  /**
   * Generates TeXML speech response and loops back to gather
   */
  static generateResponseTeXML(
    responseText: string,
    actionUrl: string = '/api/v1/voice/telnyx/respond'
  ): string {
    return `<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Gather input="speech" action="${actionUrl}" method="POST" timeout="4" speechTimeout="auto">
    <Say voice="Polly.Joanna-Neural" language="en-US">
      ${responseText}
    </Say>
  </Gather>
</Response>`;
  }
}
