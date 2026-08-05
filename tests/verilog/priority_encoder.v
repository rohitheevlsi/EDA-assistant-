// ============================================================================
// 8-Input Priority Encoder
// Returns the index of the highest-priority (MSB) active input
// Used in interrupt controllers and arbitration logic
// ============================================================================
module priority_encoder (
    input  wire [7:0] request,      // 8 input request lines
    output reg  [2:0] grant_index,  // encoded index of highest priority
    output reg        valid,        // at least one request is active
    output reg  [7:0] grant_onehot  // one-hot grant output
);

    always @(*) begin
        grant_index  = 3'b0;
        valid        = 1'b0;
        grant_onehot = 8'b0;

        casez (request)
            8'b1???????: begin grant_index = 3'd7; valid = 1'b1; grant_onehot = 8'b10000000; end
            8'b01??????: begin grant_index = 3'd6; valid = 1'b1; grant_onehot = 8'b01000000; end
            8'b001?????: begin grant_index = 3'd5; valid = 1'b1; grant_onehot = 8'b00100000; end
            8'b0001????: begin grant_index = 3'd4; valid = 1'b1; grant_onehot = 8'b00010000; end
            8'b00001???: begin grant_index = 3'd3; valid = 1'b1; grant_onehot = 8'b00001000; end
            8'b000001??: begin grant_index = 3'd2; valid = 1'b1; grant_onehot = 8'b00000100; end
            8'b0000001?: begin grant_index = 3'd1; valid = 1'b1; grant_onehot = 8'b00000010; end
            8'b00000001: begin grant_index = 3'd0; valid = 1'b1; grant_onehot = 8'b00000001; end
            default:     begin grant_index = 3'd0; valid = 1'b0; grant_onehot = 8'b00000000; end
        endcase
    end

endmodule
