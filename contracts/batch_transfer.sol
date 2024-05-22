contract BatchTransfer{

    receive() external payable {}

    function transfers(address[] memory addresses,uint256 ethAmount) public {
    for (uint i = 0; i < addresses.length; i++) {
        payable(addresses[i]).transfer(ethAmount);
    }
}
}