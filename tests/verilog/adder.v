module adder #(parameter WIDTH = 4) (
    input wire [WIDTH-1:0] a,
    input wire [WIDTH-1:0] b,
    output wire [WIDTH-1:0] sum,
    output wire cout
);
    assign {cout, sum} = a + b;
endmodule
