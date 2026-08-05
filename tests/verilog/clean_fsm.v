module clean_fsm (
    input wire clk,
    input wire rst_n,
    input wire go,
    output reg [3:0] data_out
);
    localparam IDLE = 2'b00, RUN = 2'b01, DONE = 2'b10;
    reg [1:0] state, next_state;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) state <= IDLE;
        else state <= next_state;
    end

    always @(*) begin
        case (state)
            IDLE: next_state = go ? RUN : IDLE;
            RUN:  next_state = DONE;
            DONE: next_state = IDLE;
            default: next_state = IDLE;
        endcase
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) data_out <= 4'b0;
        else if (state == RUN) data_out <= data_out + 1;
    end
endmodule
